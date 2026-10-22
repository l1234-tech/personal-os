from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class CategoryTime(BaseModel):
    category: str
    seconds: int = Field(ge=0)


class OutcomeItem(BaseModel):
    id: str
    title: str
    area: Literal["task", "study", "project", "tutoring"]
    completed_at: datetime | None = None


class MoneyTotal(BaseModel):
    currency_code: str
    amount: Decimal


class DailyAnalytics(BaseModel):
    day: date
    timezone: str
    completed_tasks: int
    completed_academic_items: int
    completed_project_milestones: int
    completed_lessons: int
    overdue_tasks: int
    tracked_seconds: int
    time_by_category: list[CategoryTime]
    tutoring_accrued: list[MoneyTotal]
    tutoring_received: list[MoneyTotal]
    outcomes: list[OutcomeItem]
    recommendations: list[str]


class WeeklyDay(BaseModel):
    day: date
    completed_outcomes: int
    tracked_seconds: int


class WeeklyAnalytics(BaseModel):
    week_start: date
    week_end: date
    timezone: str
    completed_outcomes: int
    completed_tasks: int
    completed_academic_items: int
    completed_project_milestones: int
    completed_lessons: int
    tracked_seconds: int
    time_by_category: list[CategoryTime]
    tutoring_accrued: list[MoneyTotal]
    tutoring_received: list[MoneyTotal]
    days: list[WeeklyDay]
    recommendations: list[str]
