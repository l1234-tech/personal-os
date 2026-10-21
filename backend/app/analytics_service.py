from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models_academic import AcademicItem, ProjectMilestone
from app.models_tasks import Task, TimeEntry
from app.models_tutoring import Lesson, Payment, PaymentAllocation, Student
from app.analytics_schemas import (
    AreaTime,
    DailyReport,
    OutcomeCounts,
    Recommendation,
    TutoringMetric,
    WeeklyReport,
)


def get_zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def get_bounds(anchor: datetime, timezone_name: str) -> tuple[datetime, datetime, date]:
    zone = get_zone(timezone_name)
    local_day = anchor.astimezone(zone).date()
    start = datetime.combine(local_day, time.min, tzinfo=zone).astimezone(UTC)
    end = datetime.combine(local_day + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
    return start, end, local_day


def _outcomes(db: Session, user_id: UUID, start: datetime, end: datetime) -> OutcomeCounts:
    completed_tasks = db.scalar(
        select(func.count(Task.id)).where(
            Task.user_id == user_id,
            Task.status == "done",
            Task.updated_at >= start,
            Task.updated_at < end,
        )
    )
    completed_items = db.scalar(
        select(func.count(AcademicItem.id)).where(
            AcademicItem.user_id == user_id,
            AcademicItem.status == "completed",
            AcademicItem.updated_at >= start,
            AcademicItem.updated_at < end,
        )
    )
    completed_projects = db.scalar(
        select(func.count(func.distinct(ProjectMilestone.project_id))).where(
            ProjectMilestone.user_id == user_id,
            ProjectMilestone.status == "completed",
            ProjectMilestone.created_at >= start,
            ProjectMilestone.created_at < end,
        )
    )
    completed_lessons = db.scalar(
        select(func.count(Lesson.id)).where(
            Lesson.user_id == user_id,
            Lesson.status == "completed",
            Lesson.updated_at >= start,
            Lesson.updated_at < end,
        )
    )
    return OutcomeCounts(
        tasks_completed=int(completed_tasks or 0),
        academic_items_completed=int(completed_items or 0),
        projects_with_completed_milestones=int(completed_projects or 0),
        tutoring_lessons_completed=int(completed_lessons or 0),
    )


def _time_by_area(db: Session, user_id: UUID, start: datetime, end: datetime) -> tuple[int, list[AreaTime]]:
    rows = db.execute(
        select(TimeEntry.category, func.coalesce(func.sum(TimeEntry.duration_seconds), 0))
        .where(
            TimeEntry.user_id == user_id,
            TimeEntry.started_at >= start,
            TimeEntry.started_at < end,
        )
        .group_by(TimeEntry.category)
        .order_by(func.sum(TimeEntry.duration_seconds).desc())
    ).all()
    areas = [AreaTime(category=str(category), seconds=int(seconds or 0)) for category, seconds in rows]
    return sum(area.seconds for area in areas), areas


def _tutoring_metrics(db: Session, user_id: UUID) -> list[TutoringMetric]:
    students = db.scalars(select(Student).where(Student.user_id == user_id)).all()
    result: list[TutoringMetric] = []
    for student in students:
        accrued = db.scalar(
            select(func.coalesce(func.sum(Lesson.price_amount), 0)).where(
                Lesson.user_id == user_id,
                Lesson.student_id == student.id,
                Lesson.status == "completed",
            )
        )
        received = db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.user_id == user_id, Payment.student_id == student.id
            )
        )
        allocated = db.scalar(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
            .join(Lesson, Lesson.id == PaymentAllocation.lesson_id)
            .where(
                PaymentAllocation.user_id == user_id,
                Lesson.user_id == user_id,
                Lesson.student_id == student.id,
                Lesson.status == "completed",
            )
        )
        a = Decimal(accrued or 0)
        r = Decimal(received or 0)
        l = Decimal(allocated or 0)
        result.append(
            TutoringMetric(
                currency_code=student.currency_code,
                accrued=a,
                received=r,
                allocated=l,
                debt=max(a - l, Decimal("0.00")),
            )
        )
    return result


def _deadline_rows(db: Session, user_id: UUID, start: datetime, end: datetime) -> list[dict[str, str | None]]:
    tasks = db.scalars(
        select(Task).where(
            Task.user_id == user_id,
            Task.status.notin_(("done", "cancelled")),
            Task.due_at.is_not(None),
            Task.due_at < end + timedelta(days=14),
        ).order_by(Task.due_at.asc()).limit(20)
    ).all()
    items: list[dict[str, str | None]] = [
        {"title": task.title, "due_at": task.due_at.isoformat() if task.due_at else None, "kind": "task"}
        for task in tasks
    ]
    academic = db.scalars(
        select(AcademicItem).where(
            AcademicItem.user_id == user_id,
            AcademicItem.status.notin_(("completed", "cancelled")),
            AcademicItem.due_at.is_not(None),
            AcademicItem.due_at < end + timedelta(days=14),
        ).order_by(AcademicItem.due_at.asc()).limit(20)
    ).all()
    items.extend(
        {"title": item.title, "due_at": item.due_at.isoformat() if item.due_at else None, "kind": item.item_type}
        for item in academic
    )
    return sorted(items, key=lambda row: row["due_at"] or "")[:20]


def _recommendations(
    outcomes: OutcomeCounts, time_seconds: int, deadlines: list[dict[str, str | None]],
    tutoring: list[TutoringMetric],
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    if deadlines:
        first_deadline = deadlines[0]
        recs.append(
            Recommendation(
                code="upcoming_deadline",
                message=f"Проверь ближайший дедлайн: {first_deadline['title']}.",
                reason=f"Найдены незакрытые обязательства; ближайшая дата: {first_deadline['due_at'] or 'не указана'}.",
            )
        )
    if time_seconds == 0:
        recs.append(
            Recommendation(
                code="track_actual_time",
                message="Запиши фактическое время хотя бы для одной рабочей сессии.",
                reason="Без time entries нельзя сравнить план и факт.",
            )
        )
    if outcomes.tasks_completed + outcomes.academic_items_completed + outcomes.tutoring_lessons_completed == 0:
        recs.append(
            Recommendation(
                code="define_one_outcome",
                message="Выбери один проверяемый результат на следующий рабочий блок.",
                reason="За выбранный период завершённые задачи, академические работы или занятия не зафиксированы.",
            )
        )
    if any(metric.debt > 0 for metric in tutoring):
        recs.append(
            Recommendation(
                code="review_tutoring_debt",
                message="Проверь неоплаченные или нераспределённые платежи по занятиям.",
                reason="Начисления за проведённые уроки превышают суммы платежей, распределённые по урокам.",
            )
        )
    return recs


def build_daily_report(db: Session, user_id: UUID, anchor: datetime, timezone_name: str) -> DailyReport:
    start, end, local_day = get_bounds(anchor, timezone_name)
    outcomes = _outcomes(db, user_id, start, end)
    seconds, areas = _time_by_area(db, user_id, start, end)
    deadlines = _deadline_rows(db, user_id, start, end)
    tutoring = _tutoring_metrics(db, user_id)
    return DailyReport(
        report_date=local_day,
        timezone=timezone_name,
        outcomes=outcomes,
        tracked_seconds=seconds,
        time_by_area=areas,
        upcoming_deadlines=deadlines,
        tutoring=tutoring,
        recommendations=_recommendations(outcomes, seconds, deadlines, tutoring),
        generated_at=datetime.now(UTC),
    )


def build_weekly_report(db: Session, user_id: UUID, anchor: datetime, timezone_name: str) -> WeeklyReport:
    zone = get_zone(timezone_name)
    local_date = anchor.astimezone(zone).date()
    week_start = local_date - timedelta(days=local_date.weekday())
    start = datetime.combine(week_start, time.min, tzinfo=zone).astimezone(UTC)
    end = datetime.combine(week_start + timedelta(days=7), time.min, tzinfo=zone).astimezone(UTC)
    outcomes = _outcomes(db, user_id, start, end)
    seconds, areas = _time_by_area(db, user_id, start, end)
    tutoring = _tutoring_metrics(db, user_id)
    daily: list[dict[str, int | str]] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        day_start = datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)
        day_end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
        count = db.scalar(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.status == "done",
                Task.updated_at >= day_start,
                Task.updated_at < day_end,
            )
        )
        daily.append({"date": day.isoformat(), "tasks_completed": int(count or 0)})
    deadlines = _deadline_rows(db, user_id, start, end)
    return WeeklyReport(
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        timezone=timezone_name,
        outcomes=outcomes,
        tracked_seconds=seconds,
        time_by_area=areas,
        daily_completed_tasks=daily,
        tutoring=tutoring,
        recommendations=_recommendations(outcomes, seconds, deadlines, tutoring),
        generated_at=datetime.now(UTC),
    )
