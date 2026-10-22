from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.models_academic import AcademicItem, ProjectMilestone
from app.models_tasks import Task, TimeEntry
from app.models_tutoring import Lesson, Payment
from app.analytics_schemas import (
    CategoryTime,
    DailyAnalytics,
    MoneyTotal,
    OutcomeItem,
    WeeklyAnalytics,
    WeeklyDay,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="User timezone is not valid") from exc


def day_bounds(day: date, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone)
    return start, start + timedelta(days=1)


def week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def time_totals(
    db: Session, user_id, start: datetime, end: datetime
) -> tuple[int, list[CategoryTime]]:
    entries = db.scalars(
        select(TimeEntry).where(
            TimeEntry.user_id == user_id,
            TimeEntry.started_at < end,
            TimeEntry.ended_at > start,
        )
    ).all()
    categories: dict[str, int] = defaultdict(int)
    total = 0
    for entry in entries:
        overlap_start = max(entry.started_at, start)
        overlap_end = min(entry.ended_at, end)
        seconds = max(0, int((overlap_end - overlap_start).total_seconds()))
        total += seconds
        categories[entry.category] += seconds
    return total, [
        CategoryTime(category=name, seconds=seconds)
        for name, seconds in sorted(categories.items())
    ]


def money_totals(rows) -> list[MoneyTotal]:
    totals: dict[str, Decimal] = {}
    for row in rows:
        amount = getattr(row, "amount", None)
        if amount is None:
            amount = row.price_amount
        totals[row.currency_code] = totals.get(row.currency_code, Decimal("0.00")) + amount
    return [
        MoneyTotal(currency_code=currency, amount=amount)
        for currency, amount in sorted(totals.items())
    ]


def build_daily(db: Session, user: User, day: date) -> DailyAnalytics:
    timezone = get_timezone(user.timezone)
    start, end = day_bounds(day, timezone)
    tasks = list(
        db.scalars(
            select(Task).where(
                Task.user_id == user.id,
                Task.status == "done",
                Task.completed_at >= start,
                Task.completed_at < end,
            )
        ).all()
    )
    academic = list(
        db.scalars(
            select(AcademicItem).where(
                AcademicItem.user_id == user.id,
                AcademicItem.status == "completed",
                AcademicItem.completed_at >= start,
                AcademicItem.completed_at < end,
            )
        ).all()
    )
    milestones = list(
        db.scalars(
            select(ProjectMilestone).where(
                ProjectMilestone.user_id == user.id,
                ProjectMilestone.status == "completed",
                ProjectMilestone.completed_at >= start,
                ProjectMilestone.completed_at < end,
            )
        ).all()
    )
    lessons = list(
        db.scalars(
            select(Lesson).where(
                Lesson.user_id == user.id,
                Lesson.status == "completed",
                Lesson.actual_end >= start,
                Lesson.actual_end < end,
            )
        ).all()
    )
    overdue = int(
        len(
            db.scalars(
                select(Task.id).where(
                    Task.user_id == user.id,
                    Task.status.in_(( "todo", "in_progress")),
                    Task.due_at < start,
                )
            ).all()
        )
    )
    tracked_seconds, categories = time_totals(db, user.id, start, end)
    accrued_lessons = list(
        db.scalars(
            select(Lesson).where(
                Lesson.user_id == user.id,
                Lesson.status == "completed",
                Lesson.actual_end >= start,
                Lesson.actual_end < end,
            )
        ).all()
    )
    payments = list(
        db.scalars(
            select(Payment).where(
                Payment.user_id == user.id,
                Payment.paid_at >= start,
                Payment.paid_at < end,
            )
        ).all()
    )
    outcomes = [
        OutcomeItem(id=str(row.id), title=row.title, area="task", completed_at=row.completed_at)
        for row in tasks
    ]
    outcomes.extend(
        OutcomeItem(id=str(row.id), title=row.title, area="study", completed_at=row.completed_at)
        for row in academic
    )
    outcomes.extend(
        OutcomeItem(id=str(row.id), title=row.title, area="project", completed_at=row.completed_at)
        for row in milestones
    )
    outcomes.extend(
        OutcomeItem(
            id=str(row.id),
            title="Занятие с учеником",
            area="tutoring",
            completed_at=row.actual_end,
        )
        for row in lessons
    )
    recommendations = []
    if not outcomes:
        recommendations.append(
            "В отчёте пока нет завершённых результатов. Проверь, отмечены ли выполненные задачи и занятия."
        )
    if overdue:
        recommendations.append(
            f"Есть {overdue} просроченных незавершённых задач — выбери, что перенести или выполнить первым."
        )
    if tracked_seconds == 0:
        recommendations.append("Нет записанного фактического времени; добавь записи или используй таймер.")
    if not recommendations:
        recommendations.append("Зафиксируй главный результат дня и выбери до трёх приоритетов на завтра.")
    return DailyAnalytics(
        day=day,
        timezone=user.timezone,
        completed_tasks=len(tasks),
        completed_academic_items=len(academic),
        completed_project_milestones=len(milestones),
        completed_lessons=len(lessons),
        overdue_tasks=overdue,
        tracked_seconds=tracked_seconds,
        time_by_category=categories,
        tutoring_accrued=money_totals(accrued_lessons),
        tutoring_received=money_totals(payments),
        outcomes=sorted(outcomes, key=lambda item: item.completed_at or start),
        recommendations=recommendations,
    )


@router.get("/daily", response_model=DailyAnalytics)
def daily_analytics(
    day: date | None = Query(default=None),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> DailyAnalytics:
    timezone = get_timezone(user.timezone)
    return build_daily(db, user, day or datetime.now(timezone).date())


@router.get("/weekly", response_model=WeeklyAnalytics)
def weekly_analytics(
    week_start: date | None = Query(default=None),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> WeeklyAnalytics:
    timezone = get_timezone(user.timezone)
    requested = week_start or datetime.now(timezone).date()
    start_day = week_monday(requested)
    end_day = start_day + timedelta(days=6)
    start, _ = day_bounds(start_day, timezone)
    _, end = day_bounds(end_day, timezone)

    tasks = list(
        db.scalars(
            select(Task).where(
                Task.user_id == user.id,
                Task.status == "done",
                Task.completed_at >= start,
                Task.completed_at < end,
            )
        ).all()
    )
    academic = list(
        db.scalars(
            select(AcademicItem).where(
                AcademicItem.user_id == user.id,
                AcademicItem.status == "completed",
                AcademicItem.completed_at >= start,
                AcademicItem.completed_at < end,
            )
        ).all()
    )
    milestones = list(
        db.scalars(
            select(ProjectMilestone).where(
                ProjectMilestone.user_id == user.id,
                ProjectMilestone.status == "completed",
                ProjectMilestone.completed_at >= start,
                ProjectMilestone.completed_at < end,
            )
        ).all()
    )
    lessons = list(
        db.scalars(
            select(Lesson).where(
                Lesson.user_id == user.id,
                Lesson.status == "completed",
                Lesson.actual_end >= start,
                Lesson.actual_end < end,
            )
        ).all()
    )
    payments = list(
        db.scalars(
            select(Payment).where(
                Payment.user_id == user.id,
                Payment.paid_at >= start,
                Payment.paid_at < end,
            )
        ).all()
    )
    total_seconds, categories = time_totals(db, user.id, start, end)
    days = []
    for offset in range(7):
        current_day = start_day + timedelta(days=offset)
        daily = build_daily(db, user, current_day)
        days.append(
            WeeklyDay(
                day=current_day,
                completed_outcomes=(
                    daily.completed_tasks
                    + daily.completed_academic_items
                    + daily.completed_project_milestones
                    + daily.completed_lessons
                ),
                tracked_seconds=daily.tracked_seconds,
            )
        )
    outcomes = len(tasks) + len(academic) + len(milestones) + len(lessons)
    recommendations = []
    if outcomes == 0:
        recommendations.append(
            "За неделю не зафиксировано завершённых результатов. Проверь статусы задач, работ и занятий."
        )
    if total_seconds == 0:
        recommendations.append("За неделю нет записанного фактического времени.")
    if not recommendations:
        busiest = max(days, key=lambda item: item.completed_outcomes)
        recommendations.append(
            f"Наиболее результативный день по отмеченным результатам — {busiest.day.isoformat()}. "
            "Посмотри, какие условия помогли и можно ли их повторить."
        )
    return WeeklyAnalytics(
        week_start=start_day,
        week_end=end_day,
        timezone=user.timezone,
        completed_outcomes=outcomes,
        completed_tasks=len(tasks),
        completed_academic_items=len(academic),
        completed_project_milestones=len(milestones),
        completed_lessons=len(lessons),
        tracked_seconds=total_seconds,
        time_by_category=categories,
        tutoring_accrued=money_totals(lessons),
        tutoring_received=money_totals(payments),
        days=days,
        recommendations=recommendations,
    )
