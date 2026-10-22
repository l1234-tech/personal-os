from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db import get_db
from app.models import User
from app.models_notifications import TelegramAccount, TelegramLinkToken
from app.models_jobs import BackgroundJob

router = APIRouter(prefix="/telegram", tags=["Telegram"])


@router.post("/webhook", include_in_schema=False)
def telegram_webhook(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, bool]:
    secret = settings.telegram_webhook_secret
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secret or not supplied or supplied != secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    message = payload.get("message") or payload.get("edited_message")
    if not isinstance(message, dict):
        return {"ok": True}
    text = message.get("text")
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    if not isinstance(text, str) or not isinstance(chat, dict) or not isinstance(sender, dict):
        return {"ok": True}
    chat_id = chat.get("id")
    telegram_user_id = sender.get("id")
    if not isinstance(chat_id, (int, str)) or not isinstance(telegram_user_id, (int, str)):
        return {"ok": True}

    if text.startswith("/start "):
        token = text.removeprefix("/start ").strip()
        if not 32 <= len(token) <= 128:
            return {"ok": True}
        token_hash = sha256(token.encode("utf-8")).hexdigest()
        link = db.scalar(
            select(TelegramLinkToken)
            .where(TelegramLinkToken.token_hash == token_hash)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if link is None or link.used_at is not None or link.expires_at <= now:
            return {"ok": True}
        db.add(
            BackgroundJob(
                user_id=link.user_id,
                job_type="telegram_link",
                payload={
                    "token": token,
                    "chat_id": str(chat_id),
                    "telegram_user_id": str(telegram_user_id),
                },
                idempotency_key=f"telegram-link:{token_hash}",
                status="pending",
                run_after=now,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        return {"ok": True}

    if text.strip() == "/start":
        # Bot token is never included in response text or logs.
        token_url = f"https://t.me/{settings.telegram_bot_username}" if settings.telegram_bot_username else None
        if token_url:
            # Link token is requested from Personal OS while authenticated, not minted for anonymous users.
            db.rollback()
        return {"ok": True}

    if text.strip() == "/stop":
        account = db.scalar(
            select(TelegramAccount).where(TelegramAccount.telegram_chat_id == str(chat_id))
        )
        if account is not None and account.telegram_user_id == str(telegram_user_id):
            db.delete(account)
            db.commit()
        return {"ok": True}

    return {"ok": True}


@router.get("/status")
def telegram_status(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, str | bool | None]:
    account = db.scalar(
        select(TelegramAccount).where(TelegramAccount.user_id == user.id)
    )
    return {
        "linked": account is not None,
        "telegram_user_id": account.telegram_user_id if account else None,
        "linked_at": account.linked_at.isoformat() if account else None,
    }
