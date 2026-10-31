from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PersonalCalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    color: str = Field(default="blue", pattern="^(blue|violet|green|amber|rose|gray)$")

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Event title cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("Event timestamps must include a timezone")
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        return self


class PersonalCalendarEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    color: str | None = Field(default=None, pattern="^(blue|violet|green|amber|rose|gray)$")

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Event title cannot be blank")
        return value


class PersonalCalendarEventRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    all_day: bool
    color: str
    google_calendar_id: str | None
    google_event_id: str | None
    sync_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
