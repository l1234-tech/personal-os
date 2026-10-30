from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models_integrations import Integration, IntegrationCredential

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def require_google_oauth_settings() -> tuple[str, str, str, str]:
    client_id = settings.google_client_id
    client_secret = settings.google_client_secret
    redirect_uri = settings.google_redirect_uri
    encryption_key = settings.token_encryption_key
    if not all((client_id, client_secret, redirect_uri, encryption_key)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Calendar integration is not configured on the server",
        )
    return client_id, client_secret, redirect_uri, encryption_key


def _fernet() -> Fernet:
    _, _, _, key = require_google_oauth_settings()
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token encryption is misconfigured on the server",
        ) from exc


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stored integration credentials cannot be decrypted",
        ) from exc


def get_access_token(db: Session, integration: Integration) -> str:
    credential = db.get(IntegrationCredential, integration.id)
    if credential is None:
        raise HTTPException(status_code=409, detail="Reconnect Google Calendar")
    now = datetime.now(UTC)
    if credential.expires_at and credential.expires_at > now + timedelta(seconds=60):
        return decrypt_token(credential.encrypted_access_token)

    refresh_token = credential.encrypted_refresh_token
    if not refresh_token:
        integration.status = "reauth_required"
        db.commit()
        raise HTTPException(status_code=409, detail="Reconnect Google Calendar")

    client_id, client_secret, _, _ = require_google_oauth_settings()
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": decrypt_token(refresh_token),
                    "grant_type": "refresh_token",
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google token refresh failed") from exc

    if response.status_code >= 400:
        integration.status = "reauth_required"
        db.commit()
        raise HTTPException(status_code=409, detail="Reconnect Google Calendar")

    payload: dict[str, Any] = response.json()
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(status_code=502, detail="Google returned an invalid token response")

    credential.encrypted_access_token = encrypt_token(access_token)
    expires_in = payload.get("expires_in", 3600)
    credential.expires_at = now + timedelta(seconds=int(expires_in))
    credential.updated_at = now
    if isinstance(payload.get("refresh_token"), str):
        credential.encrypted_refresh_token = encrypt_token(payload["refresh_token"])
    db.commit()
    return access_token


def google_get_json(
    access_token: str,
    url: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google Calendar request failed") from exc

    if response.status_code == 401:
        raise HTTPException(status_code=409, detail="Reconnect Google Calendar")
    if response.status_code == 403:
        raise HTTPException(status_code=403, detail="Google denied access to this calendar resource")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Google Calendar resource not found")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Google Calendar API returned an error")
    payload: dict[str, Any] = response.json()
    return payload


def calendar_events_url(calendar_id: str) -> str:
    return f"{GOOGLE_CALENDAR_API}/calendars/{quote(calendar_id, safe='')}/events"
