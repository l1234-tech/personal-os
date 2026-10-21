import json
import logging
import os
import signal
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db import SessionLocal
from app.models_jobs import BackgroundJob, Notification, OutboxEvent
from app.models_notifications import TelegramAccount, TelegramLinkToken
from app.models_tasks import Task
from app.models_tutoring import Lesson

logger = logging.getLogger("personal_os.worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
running = True


def stop_worker(*_: object) -> None:
    global running
    running = False


signal.signal(signal.SIGTERM, stop_worker)
signal.signal(signal.SIGINT, stop_worker)


def enqueue_job(
    db,
    *,
    user_id: UUID | None,
    job_type: str,
    payload: dict[str, Any],
    idempotency_key: str,
    run_after: datetime | None = None,
) -> None:
    db.add(
        BackgroundJob(
            user_id=user_id,
            job_type=job_type,
            payload=payload,
            idempotency_key=idempotency_key,
            status="pending",
            run_after=run_after or datetime.now(UTC),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def claim_next_job(db) -> BackgroundJob | None:
    now = datetime.now(UTC)
    job = db.scalar(
        select(BackgroundJob)
        .where(
            BackgroundJob.status == "pending",
            BackgroundJob.run_after <= now,
            BackgroundJob.attempts < BackgroundJob.max_attempts,
        )
        .order_by(BackgroundJob.run_after.asc(), BackgroundJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.status = "running"
    job.locked_at = now
    job.attempts += 1
    db.commit()
    db.refresh(job)
    return job


def retry_or_fail(db, job: BackgroundJob, code: str) -> None:
    job.error_code = code
    if job.attempts >= job.max_attempts:
        job.status = "failed"
        job.finished_at = datetime.now(UTC)
    else:
        job.status = "pending"
        job.run_after = datetime.now(UTC) + timedelta(seconds=min(3600, 2 ** job.attempts * 15))
    db.commit()


def telegram_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = settings.telegram_bot_token
    if not token:
        raise RuntimeError("telegram_not_configured")
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=payload,
            timeout=15.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError("telegram_api_error") from exc
    data = response.json()
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise RuntimeError("telegram_api_error")
    result = data.get("result")
    return result if isinstance(result, dict) else {}


def send_notification(db, user_id: UUID, title: str, body: str, idempotency_key: str) -> None:
    existing = db.scalar(
        select(Notification).where(Notification.idempotency_key == idempotency_key)
    )
    if existing is None:
        existing = Notification(
            user_id=user_id,
            channel="telegram",
            kind="reminder",
            title=title,
            body=body,
            status="pending",
            idempotency_key=idempotency_key,
        )
        db.add(existing)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(Notification).where(Notification.idempotency_key == idempotency_key)
            )
            if existing is None:
                return
    if existing.status == "sent":
        return

    account = db.scalar(
        select(TelegramAccount).where(TelegramAccount.user_id == user_id)
    )
    if account is None:
        existing.status = "skipped"
        existing.error_code = "telegram_not_linked"
        db.commit()
        return

    try:
        telegram_api(
            "sendMessage",
            {
                "chat_id": account.telegram_chat_id,
                "text": f"{title}\n\n{body}",
                "disable_web_page_preview": True,
            },
        )
    except RuntimeError:
        existing.status = "failed"
        existing.error_code = "telegram_delivery_failed"
        db.commit()
        raise

    existing.status = "sent"
    existing.sent_at = datetime.now(UTC)
    existing.error_code = None
    db.commit()


def process_due_reminders(db) -> None:
    now = datetime.now(UTC)
    # Notification schedule is generated idempotently using the domain item ID and reminder horizon.
    upcoming_tasks = db.scalars(
        select(Task).where(
            Task.status.notin_(("done", "cancelled")),
            Task.due_at >= now,
            Task.due_at < now + timedelta(hours=24),
        )
    ).all()
    for task in upcoming_tasks:
        send_notification(
            db,
            task.user_id,
            "Скоро дедлайн",
            f"{task.title}\nСрок: {task.due_at.isoformat() if task.due_at else 'не указан'}",
            f"task-deadline-24h:{task.id}:{task.due_at.isoformat() if task.due_at else 'none'}",
        )

    upcoming_lessons = db.scalars(
        select(Lesson).where(
            Lesson.status == "scheduled",
            Lesson.scheduled_start >= now,
            Lesson.scheduled_start < now + timedelta(hours=24),
        )
    ).all()
    for lesson in upcoming_lessons:
        send_notification(
            db,
            lesson.user_id,
            "Скоро занятие",
            f"Начало: {lesson.scheduled_start.isoformat()}",
            f"lesson-reminder-24h:{lesson.id}:{lesson.scheduled_start.isoformat()}",
        )


def handle_job(db, job: BackgroundJob) -> None:
    if job.job_type == "daily_reminders":
        process_due_reminders(db)
        job.status = "completed"
        job.finished_at = datetime.now(UTC)
        job.error_code = None
        db.commit()
        return
    if job.job_type == "telegram_link":
        token = str(job.payload.get("token", ""))
        chat_id = str(job.payload.get("chat_id", ""))
        telegram_user_id = str(job.payload.get("telegram_user_id", ""))
        if not token or not chat_id or not telegram_user_id:
            retry_or_fail(db, job, "invalid_link_payload")
            return
        token_hash = __import__("hashlib").sha256(token.encode("utf-8")).hexdigest()
        link = db.scalar(
            select(TelegramLinkToken)
            .where(TelegramLinkToken.token_hash == token_hash)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if link is None or link.used_at is not None or link.expires_at <= now:
            job.status = "failed"
            job.error_code = "invalid_or_expired_link_token"
            job.finished_at = now
            db.commit()
            return
        existing = db.scalar(
            select(TelegramAccount).where(
                TelegramAccount.user_id == link.user_id
            )
        )
        if existing is None:
            existing = TelegramAccount(
                user_id=link.user_id,
                telegram_chat_id=chat_id,
                telegram_user_id=telegram_user_id,
            )
            db.add(existing)
        else:
            existing.telegram_chat_id = chat_id
            existing.telegram_user_id = telegram_user_id
        link.used_at = now
        job.status = "completed"
        job.finished_at = now
        db.commit()
        return
    retry_or_fail(db, job, "unknown_job_type")


def tick() -> None:
    with SessionLocal() as db:
        # Sweep stale worker locks; rows are safe to retry because handlers are idempotent.
        stale = db.scalars(
            select(BackgroundJob).where(
                BackgroundJob.status == "running",
                BackgroundJob.locked_at < datetime.now(UTC) - timedelta(minutes=10),
            )
        ).all()
        for job in stale:
            job.status = "pending"
            job.locked_at = None
        if stale:
            db.commit()

        job = claim_next_job(db)
        if job is not None:
            try:
                handle_job(db, job)
            except Exception:
                logger.exception("Background job failed type=%s id=%s", job.job_type, job.id)
                db.rollback()
                current = db.get(BackgroundJob, job.id)
                if current is not None:
                    retry_or_fail(db, current, "job_handler_failed")


def main() -> None:
    logger.info("Personal OS worker started")
    while running:
        try:
            tick()
        except Exception:
            logger.exception("Worker iteration failed")
        time.sleep(5)


if __name__ == "__main__":
    main()
