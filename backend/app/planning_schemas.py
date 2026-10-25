from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TaskBlockCreate(BaseModel):
    task_id: UUID
    start_at: datetime
    end_at: datetime
    idempotency_key: UUID
    calendar_id: str | None = Field(default=None, min_length=1, max_length=1024)

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_interval(self) -> "TaskBlockCreate":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        if (self.end_at - self.start_at).total_seconds() > 24 * 60 * 60:
            raise ValueError("A planned block cannot exceed 24 hours")
        return self


class TaskBlockRead(BaseModel):
    id: UUID
    task_id: UUID
    calendar_event_id: UUID | None
    title: str
    start_at: datetime
    end_at: datetime
    status: str
    idempotency_key: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskBlockConflict(BaseModel):
    kind: str
    title: str
    start_at: datetime
    end_at: datetime
