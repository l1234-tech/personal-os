from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserSession
from app.security import hash_token

SESSION_COOKIE = "personal_os_session"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_token(token),
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    if not session or not session.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return session.user
