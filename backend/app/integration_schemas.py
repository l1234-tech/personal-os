from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IntegrationRead(BaseModel):
    id: UUID
    provider: str
    external_account_id: str
    status: str
    scopes: list[str]
    connected_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoogleConnectResponse(BaseModel):
    authorization_url: str
    expires_at: datetime


class CalendarSelectionUpdate(BaseModel):
    calendar_ids: list[str] = Field(max_length=50)

    @field_validator("calendar_ids")
    @classmethod
    def validate_calendar_ids(cls, value: list[str]) -> list[str]:
        ids = [item.strip() for item in value]
        if any(not item for item in ids):
            raise ValueError("Calendar IDs must not be blank")
        if len(ids) != len(set(ids)):
            raise ValueError("Calendar IDs must be unique")
        return ids


class CalendarListItem(BaseModel):
    id: str
    summary: str
    primary: bool = False
    access_role: str
    selected: bool = False


class CalendarEventRead(BaseModel):
    id: UUID
    calendar_id: str
    external_event_id: str
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    all_day: bool
    status: str
    html_link: str | None
    external_updated_at: datetime | None
    synced_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CalendarSyncResult(BaseModel):
    calendars_synced: int
    events_seen: int
    events_created_or_updated: int
    synced_at: datetime
