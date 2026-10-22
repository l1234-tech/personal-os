from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TaskStatus = Literal["todo", "in_progress", "done", "cancelled"]
TaskPriority = Literal["low", "medium", "high", "urgent"]


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value


class TaskCreate(BaseModel):
    project_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    category: str = Field(default="personal", min_length=1, max_length=64)
    due_at: datetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0, le=100000)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        return require_aware(value) if value is not None else None


class TaskUpdate(BaseModel):
    project_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    category: str | None = Field(default=None, min_length=1, max_length=64)
    due_at: datetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0, le=100000)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        return require_aware(value) if value is not None else None


class TaskRead(BaseModel):
    id: UUID
    project_id: UUID | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    category: str
    due_at: datetime | None
    estimated_minutes: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimeEntryCreate(BaseModel):
    task_id: UUID | None = None
    student_id: UUID | None = None
    project_id: UUID | None = None
    category: str = Field(default="personal", min_length=1, max_length=64)
    notes: str | None = Field(default=None, max_length=10000)
    started_at: datetime
    ended_at: datetime
    source: Literal["manual", "calendar_adjustment"] = "manual"

    @field_validator("started_at", "ended_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return require_aware(value)

    @model_validator(mode="after")
    def validate_range(self) -> "TimeEntryCreate":
        if self.ended_at <= self.started_at:
            raise ValueError("ended_at must be later than started_at")
        return self


class TimeEntryUpdate(BaseModel):
    task_id: UUID | None = None
    student_id: UUID | None = None
    project_id: UUID | None = None
    category: str | None = Field(default=None, min_length=1, max_length=64)
    notes: str | None = Field(default=None, max_length=10000)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0, le=31_536_000)

    @field_validator("started_at", "ended_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return require_aware(value) if value is not None else None


class TimeEntryRead(BaseModel):
    id: UUID
    task_id: UUID | None
    student_id: UUID | None
    project_id: UUID | None
    category: str
    notes: str | None
    started_at: datetime
    ended_at: datetime
    duration_seconds: int
    source: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimerStart(BaseModel):
    task_id: UUID | None = None
    student_id: UUID | None = None
    project_id: UUID | None = None
    category: str = Field(default="personal", min_length=1, max_length=64)


class TimerRead(BaseModel):
    id: UUID
    task_id: UUID | None
    student_id: UUID | None
    project_id: UUID | None
    category: str
    started_at: datetime
    status: Literal["running", "paused", "stopped"]
    elapsed_seconds: int
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
