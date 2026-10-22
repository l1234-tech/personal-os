from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LessonStatus = Literal["scheduled", "completed", "cancelled", "rescheduled", "no_show"]
StudentStatus = Literal["active", "paused", "archived"]
HomeworkStatus = Literal["assigned", "in_progress", "submitted", "reviewed", "cancelled"]


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value


class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=120)
    rate_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency_code: str = Field(min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("currency_code")
    @classmethod
    def currency_upper(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("Currency code must contain three letters")
        return value.upper()


class StudentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    subject: str | None = Field(default=None, min_length=1, max_length=120)
    rate_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=10000)
    status: StudentStatus | None = None


class StudentRead(BaseModel):
    id: UUID
    name: str
    subject: str
    rate_amount: Decimal
    currency_code: str
    notes: str | None
    status: StudentStatus
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LessonCreate(BaseModel):
    scheduled_start: datetime
    scheduled_end: datetime
    price_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("scheduled_start", "scheduled_end")
    @classmethod
    def require_aware(cls, value: datetime) -> datetime:
        return aware(value)

    @model_validator(mode="after")
    def valid_interval(self) -> "LessonCreate":
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("scheduled_end must be later than scheduled_start")
        return self


class LessonUpdate(BaseModel):
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    status: LessonStatus | None = None
    price_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    cancellation_reason: str | None = Field(default=None, max_length=500)

    @field_validator("scheduled_start", "scheduled_end", "actual_start", "actual_end")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        return aware(value) if value is not None else None


class LessonRead(BaseModel):
    id: UUID
    student_id: UUID
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: datetime | None
    actual_end: datetime | None
    status: LessonStatus
    price_amount: Decimal
    currency_code: str
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LessonTopicCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    notes: str | None = Field(default=None, max_length=10000)


class HomeworkCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    lesson_id: UUID | None = None
    due_at: datetime | None = None

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        return aware(value) if value is not None else None


class HomeworkUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    due_at: datetime | None = None
    status: HomeworkStatus | None = None
    result_notes: str | None = Field(default=None, max_length=10000)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        return aware(value) if value is not None else None


class HomeworkRead(BaseModel):
    id: UUID
    student_id: UUID
    lesson_id: UUID | None
    title: str
    description: str | None
    due_at: datetime | None
    status: HomeworkStatus
    result_notes: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProgressCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    mastery_status: Literal["not_started", "learning", "practicing", "mastered"] = "not_started"
    notes: str | None = Field(default=None, max_length=10000)


class ProgressRead(BaseModel):
    id: UUID
    student_id: UUID
    topic: str
    mastery_status: str
    notes: str | None
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    student_id: UUID
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency_code: str = Field(min_length=3, max_length=3)
    paid_at: datetime
    method: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("currency_code")
    @classmethod
    def currency_upper(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("Currency code must contain three letters")
        return value.upper()

    @field_validator("paid_at")
    @classmethod
    def validate_paid_at(cls, value: datetime) -> datetime:
        return aware(value)


class AllocationCreate(BaseModel):
    lesson_id: UUID
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class PaymentRead(BaseModel):
    id: UUID
    student_id: UUID
    amount: Decimal
    currency_code: str
    paid_at: datetime
    method: str | None
    notes: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TutoringSummary(BaseModel):
    student_id: UUID
    currency_code: str
    accrued: Decimal
    received: Decimal
    allocated: Decimal
    debt: Decimal
    completed_lessons: int
