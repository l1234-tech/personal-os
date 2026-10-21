import hmac
import secrets
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db import get_db
from app.integration_schemas import (
    CalendarEventRead,
    CalendarListItem,
    CalendarSelectionUpdate,
    CalendarSyncResult,
    GoogleConnectResponse,
    IntegrationRead,
)
from app.integrations.google_calendar import (
    GOOGLE_CALENDAR_API,
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
    decrypt_token,
    encrypt_token,
    get_access_token,
    google_get_json,
    require_google_oauth_settings,
)
from app.models import User
from app.models_integrations import (
    CalendarEvent,
    CalendarSelection,
    Integration,
    IntegrationCredential,
    OAuthState,
    SyncCursor,
)
from app.security import generate_opaque_token, hash_token

router = APIRouter(prefix="/integrations", tags=["integrations"])
GOOGLE_PROVIDER = "google_calendar"
GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.owned",
]
OAUTH_STATE_TTL = timedelta(minutes=10)
SYNC_RESOURCE_PREFIX = "google_calendar:"


def _google_integration(db: Session, user_id, *, lock: bool = False) -> Integration:
    query = select(Integration).where(
        Integration.user_id == user_id,
        Integration.provider == GOOGLE_PROVIDER,
    )
    if lock:
        query = query.with_for_update()
    integration = db.scalar(query)
    if integration is None:
        raise HTTPException(status_code=404, detail="Google Calendar is not connected")
    if integration.status != "active":
        raise HTTPException(status_code=409, detail="Reconnect Google Calendar")
    return integration


def _aware_google_datetime(value: str, tz_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Google returned an invalid event time") from exc
    if parsed.tzinfo is None:
        try:
            zone = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(UTC)


def _event_times(event: dict, timezone_name: str) -> tuple[datetime | None, datetime | None, bool]:
    start = event.get("start") or {}
    end = event.get("end") or {}
    if isinstance(start.get("dateTime"), str) and isinstance(end.get("dateTime"), str):
        return (
            _aware_google_datetime(start["dateTime"], start.get("timeZone") or timezone_name),
            _aware_google_datetime(end["dateTime"], end.get("timeZone") or timezone_name),
            False,
        )
    if isinstance(start.get("date"), str) and isinstance(end.get("date"), str):
        try:
            first = date.fromisoformat(start["date"])
            last = date.fromisoformat(end["date"])
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Google returned an invalid all-day event") from exc
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        return (
            datetime.combine(first, time.min, tzinfo=zone).astimezone(UTC),
            datetime.combine(last, time.min, tzinfo=zone).astimezone(UTC),
            True,
        )
    return None, None, False


def _google_error_message(response: httpx.Response) -> str:
    if response.status_code == 401:
        return "Google authorization expired; reconnect Calendar"
    if response.status_code == 403:
        return "Google denied the requested Calendar permission"
    if response.status_code == 429:
        return "Google Calendar quota reached; retry later"
    return "Google Calendar request failed"


def _validate_google_response(response: httpx.Response) -> dict:
    if response.status_code >= 400:
        raise HTTPException(
            status_code=409 if response.status_code in (401, 403) else 502,
            detail=_google_error_message(response),
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Google returned an invalid response")
    return payload


def _integration_token(db: Session, integration: Integration) -> str:
    try:
        return get_access_token(db, integration)
    except HTTPException:
        raise


@router.get("", response_model=list[IntegrationRead])
def list_integrations(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[Integration]:
    return list(
        db.scalars(
            select(Integration)
            .where(Integration.user_id == user.id)
            .order_by(Integration.connected_at.desc())
        ).all()
    )


@router.post("/google/connect", response_model=GoogleConnectResponse)
def connect_google_calendar(
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> GoogleConnectResponse:
    client_id, _, redirect_uri, _ = require_google_oauth_settings()
    state = generate_opaque_token()
    expires = datetime.now(UTC) + OAUTH_STATE_TTL
    db.add(
        OAuthState(
            user_id=user.id,
            provider=GOOGLE_PROVIDER,
            state_hash=hash_token(state),
            expires_at=expires,
        )
    )
    db.commit()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    response.headers["Cache-Control"] = "no-store"
    return GoogleConnectResponse(
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params),
        expires_at=expires,
    )


@router.get("/google/callback", include_in_schema=False)
def google_oauth_callback(
    request: Request,
    code: str | None = Query(default=None, min_length=1),
    state: str | None = Query(default=None, min_length=32),
    error: str | None = None,
    db: Session = Depends(get_db),  # noqa: B008
) -> RedirectResponse:
    if error:
        return RedirectResponse(
            url=f"{settings.frontend_origin.rstrip('/')}/?google_calendar=denied",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if not code or not state:
        raise HTTPException(status_code=400, detail="OAuth callback is missing required parameters")
    client_id, client_secret, redirect_uri, _ = require_google_oauth_settings()
    state_row = db.scalar(
        select(OAuthState)
        .where(
            OAuthState.provider == GOOGLE_PROVIDER,
            OAuthState.state_hash == hash_token(state),
        )
        .with_for_update()
    )
    now = datetime.now(UTC)
    if (
        state_row is None
        or state_row.used_at is not None
        or state_row.expires_at <= now
    ):
        raise HTTPException(status_code=400, detail="OAuth state is invalid or expired")

    state_row.used_at = now
    try:
        with httpx.Client(timeout=20.0) as client:
            token_response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_data = _validate_google_response(token_response)
            access_token = token_data.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise HTTPException(status_code=502, detail="Google did not return an access token")
            identity_response = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            identity = _validate_google_response(identity_response)
    except httpx.HTTPError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="Could not reach Google OAuth service") from exc
    except Exception:
        db.rollback()
        raise

    external_id = identity.get("sub")
    if not isinstance(external_id, str) or not external_id:
        db.rollback()
        raise HTTPException(status_code=502, detail="Google identity response is incomplete")

    integration = db.scalar(
        select(Integration).where(
            Integration.user_id == state_row.user_id,
            Integration.provider == GOOGLE_PROVIDER,
        )
    )
    if integration is None:
        integration = Integration(
            user_id=state_row.user_id,
            provider=GOOGLE_PROVIDER,
            external_account_id=external_id,
            status="active",
            scopes=GOOGLE_SCOPES,
        )
        db.add(integration)
        db.flush()
    else:
        integration.external_account_id = external_id
        integration.status = "active"
        integration.scopes = GOOGLE_SCOPES
    db.flush()

    expires_in = token_data.get("expires_in", 3600)
    refresh_token = token_data.get("refresh_token")
    existing_credential = db.get(IntegrationCredential, integration.id)
    encrypted_refresh = (
        encrypt_token(refresh_token)
        if isinstance(refresh_token, str) and refresh_token
        else (existing_credential.encrypted_refresh_token if existing_credential else None)
    )
    if not encrypted_refresh:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Google did not provide a refresh token. Disconnect access and reconnect with consent.",
        )
    if existing_credential is None:
        existing_credential = IntegrationCredential(
            integration_id=integration.id,
            encrypted_access_token=encrypt_token(access_token),
            encrypted_refresh_token=encrypted_refresh,
            expires_at=now + timedelta(seconds=int(expires_in)),
            token_type=str(token_data.get("token_type", "Bearer")),
        )
        db.add(existing_credential)
    else:
        existing_credential.encrypted_access_token = encrypt_token(access_token)
        existing_credential.encrypted_refresh_token = encrypted_refresh
        existing_credential.expires_at = now + timedelta(seconds=int(expires_in))
        existing_credential.token_type = str(token_data.get("token_type", "Bearer"))
        existing_credential.updated_at = now
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Google Calendar connection could not be saved") from exc
    return RedirectResponse(
        url=f"{settings.frontend_origin.rstrip('/')}/?google_calendar=connected",
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/google/calendars", response_model=list[CalendarListItem])
def get_google_calendars(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[CalendarListItem]:
    integration = _google_integration(db, user.id)
    access_token = _integration_token(db, integration)
    payload = google_get_json(access_token, f"{GOOGLE_CALENDAR_API}/users/me/calendarList", {"maxResults": "250"})
    calendars = payload.get("items", [])
    if not isinstance(calendars, list):
        raise HTTPException(status_code=502, detail="Google returned an invalid calendar list")
    selected_rows = list(
        db.scalars(
            select(CalendarSelection).where(CalendarSelection.integration_id == integration.id)
        ).all()
    )
    selected_by_id = {item.calendar_id: item for item in selected_rows}
    results: list[CalendarListItem] = []
    for item in calendars:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        calendar_id = item["id"]
        results.append(
            CalendarListItem(
                id=calendar_id,
                summary=str(item.get("summary") or calendar_id),
                primary=bool(item.get("primary", False)),
                access_role=str(item.get("accessRole", "reader")),
                selected=bool(selected_by_id.get(calendar_id) and selected_by_id[calendar_id].selected),
            )
        )
    return results


@router.put("/google/calendars", response_model=list[CalendarListItem])
def set_google_calendars(
    payload: CalendarSelectionUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[CalendarListItem]:
    integration = _google_integration(db, user.id, lock=True)
    access_token = _integration_token(db, integration)
    remote = google_get_json(
        access_token,
        f"{GOOGLE_CALENDAR_API}/users/me/calendarList",
        {"maxResults": "250"},
    )
    remote_items = remote.get("items", [])
    if not isinstance(remote_items, list):
        raise HTTPException(status_code=502, detail="Google returned an invalid calendar list")
    available = {
        str(item["id"]): str(item.get("summary") or item["id"])
        for item in remote_items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    unknown = set(payload.calendar_ids) - set(available)
    if unknown:
        raise HTTPException(status_code=422, detail="Selection contains a calendar not accessible to this account")

    existing_rows = list(
        db.scalars(
            select(CalendarSelection).where(CalendarSelection.integration_id == integration.id)
        ).all()
    )
    by_id = {item.calendar_id: item for item in existing_rows}
    now = datetime.now(UTC)
    for calendar_id, summary in available.items():
        row = by_id.get(calendar_id)
        if row is None:
            row = CalendarSelection(
                integration_id=integration.id,
                calendar_id=calendar_id,
                summary=summary,
                selected=calendar_id in payload.calendar_ids,
                updated_at=now,
            )
            db.add(row)
        else:
            row.summary = summary
            row.selected = calendar_id in payload.calendar_ids
            row.updated_at = now
    db.commit()
    return [
        CalendarListItem(
            id=calendar_id,
            summary=available[calendar_id],
            primary=any(
                isinstance(item, dict) and item.get("id") == calendar_id and item.get("primary", False)
                for item in remote_items
            ),
            access_role=next(
                (str(item.get("accessRole", "reader")) for item in remote_items if isinstance(item, dict) and item.get("id") == calendar_id),
                "reader",
            ),
            selected=calendar_id in payload.calendar_ids,
        )
        for calendar_id in available
    ]


@router.post("/google/sync", response_model=CalendarSyncResult)
def sync_google_calendars(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> CalendarSyncResult:
    integration = _google_integration(db, user.id, lock=True)
    access_token = _integration_token(db, integration)
    selected = list(
        db.scalars(
            select(CalendarSelection).where(
                CalendarSelection.integration_id == integration.id,
                CalendarSelection.selected.is_(True),
            )
        ).all()
    )
    if not selected:
        raise HTTPException(status_code=409, detail="Select at least one calendar before syncing")

    calendars_synced = 0
    seen = 0
    changed = 0
    now = datetime.now(UTC)
    try:
        zone_name = user.timezone
        ZoneInfo(zone_name)
    except ZoneInfoNotFoundError:
        zone_name = "UTC"

    for selection in selected:
        resource_type = SYNC_RESOURCE_PREFIX + selection.calendar_id
        cursor_row = db.scalar(
            select(SyncCursor)
            .where(
                SyncCursor.integration_id == integration.id,
                SyncCursor.resource_type == resource_type,
            )
            .with_for_update()
        )
        if cursor_row is None:
            cursor_row = SyncCursor(
                integration_id=integration.id,
                resource_type=resource_type,
                cursor=None,
            )
            db.add(cursor_row)
            db.flush()

        params: dict[str, str] = {"maxResults": "2500", "showDeleted": "true"}
        if cursor_row.cursor:
            params["syncToken"] = cursor_row.cursor
        else:
            params["timeMin"] = (now - timedelta(days=90)).isoformat().replace("+00:00", "Z")
            params["timeMax"] = (now + timedelta(days=365)).isoformat().replace("+00:00", "Z")
            params["singleEvents"] = "true"
            params["orderBy"] = "startTime"

        url = f"{GOOGLE_CALENDAR_API}/calendars/{__import__('urllib.parse', fromlist=['quote']).quote(selection.calendar_id, safe='')}/events"
        page_token: str | None = None
        next_sync_token: str | None = None
        while True:
            page_params = dict(params)
            if page_token:
                page_params["pageToken"] = page_token
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(
                        url,
                        headers={"Authorization": f"Bearer {access_token}"},
                        params=page_params,
                    )
            except httpx.HTTPError as exc:
                db.rollback()
                raise HTTPException(status_code=502, detail="Google Calendar sync failed") from exc
            if response.status_code == 410 and cursor_row.cursor:
                cursor_row.cursor = None
                db.flush()
                db.commit()
                return sync_google_calendars(db=db, user=user)
            if response.status_code in (401, 403, 429) or response.status_code >= 500:
                db.rollback()
                raise HTTPException(
                    status_code=409 if response.status_code in (401, 403) else 502,
                    detail=_google_error_message(response),
                )
            response_data = _validate_google_response(response)
            items = response_data.get("items", [])
            if not isinstance(items, list):
                db.rollback()
                raise HTTPException(status_code=502, detail="Google returned an invalid event list")
            seen += len(items)
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                    continue
                event_id = item["id"]
                event = db.scalar(
                    select(CalendarEvent).where(
                        CalendarEvent.integration_id == integration.id,
                        CalendarEvent.calendar_id == selection.calendar_id,
                        CalendarEvent.external_event_id == event_id,
                    )
                )
                event_status = str(item.get("status") or "confirmed")
                start_at, end_at, all_day = _event_times(item, zone_name)
                if event_status == "cancelled":
                    if event:
                        event.status = "cancelled"
                        event.external_updated_at = (
                            _aware_google_datetime(item["updated"], zone_name)
                            if isinstance(item.get("updated"), str)
                            else event.external_updated_at
                        )
                        event.synced_at = now
                        changed += 1
                    continue
                if start_at is None or end_at is None or end_at <= start_at:
                    continue
                if event is None:
                    event = CalendarEvent(
                        user_id=user.id,
                        integration_id=integration.id,
                        calendar_id=selection.calendar_id,
                        external_event_id=event_id,
                        title=str(item.get("summary") or "(без названия)")[:1000],
                        description=item.get("description") if isinstance(item.get("description"), str) else None,
                        start_at=start_at,
                        end_at=end_at,
                        all_day=all_day,
                        status=event_status,
                        html_link=item.get("htmlLink") if isinstance(item.get("htmlLink"), str) else None,
                        external_updated_at=(
                            _aware_google_datetime(item["updated"], zone_name)
                            if isinstance(item.get("updated"), str)
                            else None
                        ),
                        synced_at=now,
                    )
                    db.add(event)
                    changed += 1
                else:
                    event.title = str(item.get("summary") or "(без названия)")[:1000]
                    event.description = item.get("description") if isinstance(item.get("description"), str) else None
                    event.start_at = start_at
                    event.end_at = end_at
                    event.all_day = all_day
                    event.status = event_status
                    event.html_link = item.get("htmlLink") if isinstance(item.get("htmlLink"), str) else None
                    event.external_updated_at = (
                        _aware_google_datetime(item["updated"], zone_name)
                        if isinstance(item.get("updated"), str)
                        else None
                    )
                    event.synced_at = now
                    changed += 1
            page_token_value = response_data.get("nextPageToken")
            page_token = page_token_value if isinstance(page_token_value, str) else None
            next_token_value = response_data.get("nextSyncToken")
            if isinstance(next_token_value, str):
                next_sync_token = next_token_value
            if not page_token:
                break
        if next_sync_token:
            cursor_row.cursor = next_sync_token
        cursor_row.last_synced_at = now
        calendars_synced += 1
        db.flush()
    db.commit()
    return CalendarSyncResult(
        calendars_synced=calendars_synced,
        events_seen=seen,
        events_created_or_updated=changed,
        synced_at=now,
    )


@router.get("/calendar/events", response_model=list[CalendarEventRead])
def list_calendar_events(
    start_at: datetime = Query(...),
    end_at: datetime = Query(...),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[CalendarEvent]:
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at <= start_at:
        raise HTTPException(status_code=422, detail="A valid timezone-aware interval is required")
    return list(
        db.scalars(
            select(CalendarEvent)
            .where(
                CalendarEvent.user_id == user.id,
                CalendarEvent.start_at < end_at,
                CalendarEvent.end_at > start_at,
            )
            .order_by(CalendarEvent.start_at.asc())
            .limit(limit)
        ).all()
    )
