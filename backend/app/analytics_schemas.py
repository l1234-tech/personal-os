from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class OutcomeCounts(BaseModel):
    tasks_completed: int
    academic_items_completed: int
    projects_with_completed_milestones: int
    tutoring_lessons_completed: int


class AreaTime(BaseModel):
    category: str
    seconds: int


class TutoringMetric(BaseModel):
    currency_code: str
    accrued: Decimal
    received: Decimal
    allocated: Decimal
    debt: Decimal


class Recommendation(BaseModel):
    code: str
    message: str
    reason: str


class DailyReport(BaseModel):
    report_date: date
    timezone: str
    outcomes: OutcomeCounts
    tracked_seconds: int
    time_by_area: list[AreaTime]
    upcoming_deadlines: list[dict[str, str | None]]
    tutoring: list[TutoringMetric]
    recommendations: list[Recommendation]
    generated_at: datetime


class WeeklyReport(BaseModel):
    week_start: date
    week_end: date
    timezone: str
    outcomes: OutcomeCounts
    tracked_seconds: int
    time_by_area: list[AreaTime]
    daily_completed_tasks: list[dict[str, int | str]]
    tutoring: list[TutoringMetric]
    recommendations: list[Recommendation]
    generated_at: datetime
