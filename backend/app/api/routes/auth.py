import hmac
import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import SESSION_COOKIE, get_current_user
from app.core.config import settings
from app.db import get_db
from app.models import Invitation, User, UserSession
from app.schemas import (
    CreateInvitationRequest,
    InvitationResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.security import generate_opaque_token, hash_password, hash_token, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SESSION_TTL = timedelta(days=14)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    return normalized


def enforce_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != settings.frontend_origin.rstrip("/"):
        raise HTTPException(status_code=403, detail="Request origin is not allowed")


def issue_session(db: Session, user: User, response: Response) -> None:
    token = generate_opaque_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + SESSION_TTL,
        )
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008
) -> User:
    enforce_same_origin(request)
    email = normalize_email(payload.email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Registration could not be completed")

    invitation = db.scalar(
        select(Invitation)
        .where(Invitation.token_hash == hash_token(payload.invitation_token))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if (
        invitation is None
        or invitation.used_at is not None
        or invitation.expires_at <= now
        or invitation.email.strip().lower() != email
    ):
        raise HTTPException(status_code=400, detail="Invitation is invalid or expired")

    user = User(email=email, password_hash=hash_password(payload.password))
    invitation.used_at = now
    db.add(user)
    try:
        db.flush()
        issue_session(db, user, response)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        response.delete_cookie(SESSION_COOKIE, path="/", samesite="lax")
        raise HTTPException(
            status_code=409, detail="Registration could not be completed"
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    enforce_same_origin(request)
    email = normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    issue_session(db, user, response)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    enforce_same_origin(request)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:  # noqa: B008
    return user


@router.post("/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(
    payload: CreateInvitationRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> InvitationResponse:
    if not settings.bootstrap_invitation_secret:
        raise HTTPException(status_code=404, detail="Not found")
    enforce_same_origin(request)
    supplied = request.headers.get("x-bootstrap-secret", "")
    if not hmac.compare_digest(supplied, settings.bootstrap_invitation_secret):
        raise HTTPException(status_code=403, detail="Forbidden")
    email = normalize_email(payload.email)
    token = generate_opaque_token()
    expires = datetime.now(UTC) + timedelta(hours=payload.expires_in_hours)
    db.add(Invitation(email=email, token_hash=hash_token(token), expires_at=expires))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return InvitationResponse(token=token, email=email, expires_at=expires)
