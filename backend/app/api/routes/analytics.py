from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.models_integrations import Integration, IntegrationCredential
from app.models_academic import Project, ProjectRepository
from app.models_notifications import Notification, TelegramLinkToken
from app.models_jobs import BackgroundJob
from app.models_audit import AuditLog
from app.models_tasks import Task, TimeEntry
from app.models_tutoring import Lesson, Payment, Student
from app.models_academic import AcademicItem
from app.analytics_schemas import (
    DailyReport,
    WeeklyReport,
    OutcomeCounts,
    AreaTime,
    TutoringMetric,
    Recommendation,
)
from app.analytics_service import build_daily_report, build_weekly_report

router = APIRouter(tags=["analytics and automation"])


@router.get("/analytics/daily", response_model=DailyReport)
def daily_report(
    report_date: datetime | None = Query(default=None, description="Timezone-aware local date/time"),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> DailyReport:
    anchor = report_date or datetime.now(UTC)
    if anchor.tzinfo is None or anchor.utcoffset() is None:
        raise HTTPException(status_code=422, detail="report_date must include a timezone")
    return build_daily_report(db, user.id, anchor.astimezone(UTC), user.timezone)


@router.get("/analytics/weekly", response_model=WeeklyReport)
def weekly_report(
    week_start: datetime | None = Query(default=None, description="Timezone-aware week start"),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> WeeklyReport:
    anchor = week_start or datetime.now(UTC)
    if anchor.tzinfo is None or anchor.utcoffset() is None:
        raise HTTPException(status_code=422, detail="week_start must include a timezone")
    return build_weekly_report(db, user.id, anchor.astimezone(UTC), user.timezone)


@router.get("/analytics/summary", response_model=OutcomeCounts)
def analytics_summary(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> OutcomeCounts:
    return build_daily_report(db, user.id, datetime.now(UTC), user.timezone).outcomes


@router.get("/automation/jobs")
def list_recent_jobs(
    limit: int = Query(default=50, ge=1, le=200),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[dict[str, str | None]]:
    jobs = db.scalars(
        select(BackgroundJob)
        .where(BackgroundJob.user_id == user.id)
        .order_by(BackgroundJob.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(job.id),
            "job_type": job.job_type,
            "status": job.status,
            "error_code": job.error_code,
            "created_at": job.created_at.isoformat(),
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }
        for job in jobs
    ]


@router.post("/notifications/telegram/link")
def create_telegram_link_token(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, str]:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    row = TelegramLinkToken(
        user_id=user.id,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        expires_at=now + timedelta(minutes=15),
    )
    db.add(row)
    db.commit()
    return {"token": token, "expires_at": row.expires_at.isoformat()}


@router.get("/notifications")
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=100, ge=1, le=300),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[dict[str, str | None]]:
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()
    if unread_only:
        rows = [row for row in rows if row.read_at is None]
    return [
        {
            "id": str(row.id),
            "channel": row.channel,
            "kind": row.kind,
            "title": row.title,
            "body": row.body,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.read_at = datetime.now(UTC)
    db.commit()
