from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value


class TaskBlockCreate(BaseModel):
    task_id: UUID
    start_at: datetime
    end_at: datetime

    @field_validator("start_at", "end_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return require_aware(value)

    @model_validator(mode="after")
    def validate_range(self) -> "TaskBlockCreate":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        return self


class TaskBlockUpdate(BaseModel):
    start_at: datetime | None = None
    end_at: datetime | None = None

    @field_validator("start_at", "end_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return require_aware(value) if value is not None else None


class TaskBlockRead(BaseModel):
    id: UUID
    task_id: UUID
    title: str
    start_at: datetime
    end_at: datetime
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
