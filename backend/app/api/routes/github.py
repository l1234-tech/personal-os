from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db import get_db
from app.models import User
from app.models_academic import Project, ProjectRepository
from app.models_integrations import Integration, IntegrationCredential, OAuthState
from app.security import generate_opaque_token, hash_token
from app.github_schemas import GitHubActivitySummary, GitHubRepositoryLink, GitHubRepositorySummary

router = APIRouter(prefix="/integrations/github", tags=["GitHub"])
PROVIDER = "github"
SCOPES = "read:user public_repo"
AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_URL = "https://api.github.com"


def _github_settings() -> tuple[str, str, str, str]:
    client_id = settings.github_client_id
    client_secret = settings.github_client_secret
    redirect_uri = settings.github_redirect_uri
    encryption_key = settings.token_encryption_key
    if not client_id or not client_secret or not redirect_uri or not encryption_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub integration is not configured on the server",
        )
    return client_id, client_secret, redirect_uri, encryption_key


def _encrypt(value: str) -> str:
    _, _, _, key = _github_settings()
    try:
        return Fernet(key.encode("utf-8")).encrypt(value.encode("utf-8")).decode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Token encryption is misconfigured") from exc


def _decrypt(value: str) -> str:
    _, _, _, key = _github_settings()
    try:
        return Fernet(key.encode("utf-8")).decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Stored GitHub credential cannot be decrypted") from exc


def _request_json(method: str, url: str, token: str, *, payload: dict[str, Any] | None = None,
                  params: dict[str, str] | None = None) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "PersonalOS",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.request(method, url, headers=headers, params=params, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="GitHub API request failed") from exc
    if response.status_code in (401, 403):
        detail = "GitHub authorization expired or permission was denied"
        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            detail = "GitHub API rate limit reached; retry later"
        raise HTTPException(status_code=409 if response.status_code == 401 else 403, detail=detail)
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="GitHub resource not found")
    if response.status_code == 429:
        raise HTTPException(status_code=429, detail="GitHub API rate limit reached; retry later")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="GitHub API returned an error")
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="GitHub returned an invalid response") from exc


def _integration(db: Session, user_id: UUID) -> Integration:
    row = db.scalar(
        select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider == PROVIDER,
            Integration.status == "active",
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="GitHub is not connected")
    credential = db.get(IntegrationCredential, row.id)
    if credential is None:
        raise HTTPException(status_code=409, detail="Reconnect GitHub")
    if credential.expires_at and credential.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=409, detail="GitHub token expired; reconnect GitHub")
    return row


def _token(db: Session, integration: Integration) -> str:
    credential = db.get(IntegrationCredential, integration.id)
    if credential is None:
        raise HTTPException(status_code=409, detail="Reconnect GitHub")
    return _decrypt(credential.encrypted_access_token)


@router.post("/connect")
def start_github_oauth(
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, str]:
    client_id, _, redirect_uri, _ = _github_settings()
    raw_state = generate_opaque_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    db.add(
        OAuthState(
            user_id=user.id,
            provider=PROVIDER,
            state_hash=hash_token(raw_state),
            expires_at=expires_at,
        )
    )
    db.commit()
    query = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": raw_state,
        "allow_signup": "false",
    })
    response.headers["Cache-Control"] = "no-store"
    return {"authorization_url": f"{AUTHORIZE_URL}?{query}", "expires_at": expires_at.isoformat()}


@router.get("/callback", include_in_schema=False)
def github_oauth_callback(
    code: str | None = Query(default=None, min_length=1),
    state: str | None = Query(default=None, min_length=32),
    error: str | None = None,
    db: Session = Depends(get_db),  # noqa: B008
) -> RedirectResponse:
    if error:
        return RedirectResponse(
            f"{settings.frontend_origin.rstrip('/')}/?github=denied",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if not code or not state:
        raise HTTPException(status_code=400, detail="OAuth callback is missing required parameters")
    client_id, client_secret, redirect_uri, _ = _github_settings()
    state_row = db.scalar(
        select(OAuthState).where(
            OAuthState.provider == PROVIDER,
            OAuthState.state_hash == hash_token(state),
        ).with_for_update()
    )
    now = datetime.now(UTC)
    if state_row is None or state_row.used_at is not None or state_row.expires_at <= now:
        raise HTTPException(status_code=400, detail="OAuth state is invalid or expired")
    try:
        with httpx.Client(timeout=20.0) as client:
            token_response = client.post(
                TOKEN_URL,
                headers={"Accept": "application/json", "User-Agent": "PersonalOS"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "state": state,
                },
            )
            if token_response.status_code >= 400:
                raise HTTPException(status_code=502, detail="GitHub OAuth token exchange failed")
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise HTTPException(status_code=502, detail="GitHub did not return an access token")
            identity_response = client.get(
                f"{API_URL}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "PersonalOS",
                },
            )
            if identity_response.status_code >= 400:
                raise HTTPException(status_code=502, detail="GitHub identity lookup failed")
            identity = identity_response.json()
    except httpx.HTTPError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="Could not reach GitHub OAuth service") from exc
    if not isinstance(identity, dict) or not isinstance(identity.get("id"), int):
        db.rollback()
        raise HTTPException(status_code=502, detail="GitHub identity response is incomplete")

    state_row.used_at = now
    external_id = str(identity["id"])
    integration = db.scalar(
        select(Integration).where(
            Integration.user_id == state_row.user_id,
            Integration.provider == PROVIDER,
        )
    )
    if integration is None:
        integration = Integration(
            user_id=state_row.user_id,
            provider=PROVIDER,
            external_account_id=external_id,
            status="active",
            scopes=SCOPES.split(),
        )
        db.add(integration)
        db.flush()
    else:
        integration.external_account_id = external_id
        integration.status = "active"
        integration.scopes = SCOPES.split()
    db.flush()

    expires_at = None
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    if isinstance(expires_in, int) and expires_in > 0:
        expires_at = now + timedelta(seconds=expires_in)
    credential = db.get(IntegrationCredential, integration.id)
    encrypted_refresh = (
        _encrypt(refresh_token)
        if isinstance(refresh_token, str) and refresh_token
        else (credential.encrypted_refresh_token if credential else None)
    )
    if credential is None:
        credential = IntegrationCredential(
            integration_id=integration.id,
            encrypted_access_token=_encrypt(access_token),
            encrypted_refresh_token=encrypted_refresh,
            expires_at=expires_at,
            token_type=str(token_data.get("token_type") or "Bearer"),
        )
        db.add(credential)
    else:
        credential.encrypted_access_token = _encrypt(access_token)
        credential.encrypted_refresh_token = encrypted_refresh
        credential.expires_at = expires_at
        credential.token_type = str(token_data.get("token_type") or "Bearer")
        credential.updated_at = now
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="GitHub connection could not be saved") from exc
    return RedirectResponse(
        f"{settings.frontend_origin.rstrip('/')}/?github=connected",
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/repos", response_model=list[GitHubRepositorySummary])
def list_github_repositories(
    limit: int = Query(default=100, ge=1, le=100),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[GitHubRepositorySummary]:
    integration = _integration(db, user.id)
    token = _token(db, integration)
    result = _request_json(
        "GET",
        f"{API_URL}/user/repos",
        token,
        params={"visibility": "public", "affiliation": "owner,collaborator,organization_member", "sort": "updated", "per_page": str(limit)},
    )
    if not isinstance(result, list):
        raise HTTPException(status_code=502, detail="GitHub returned an invalid repository list")
    linked_rows = db.scalars(
        select(ProjectRepository).where(ProjectRepository.user_id == user.id)
    ).all()
    project_links = {str(row.external_repo_id): str(row.project_id) for row in linked_rows}
    rows: list[GitHubRepositorySummary] = []
    for item in result:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            continue
        rows.append(
            GitHubRepositorySummary(
                id=item["id"],
                name=str(item.get("name") or ""),
                full_name=str(item.get("full_name") or ""),
                html_url=str(item.get("html_url") or ""),
                private=bool(item.get("private", False)),
                default_branch=str(item.get("default_branch") or "main"),
                pushed_at=item.get("pushed_at") if isinstance(item.get("pushed_at"), str) else None,
                linked_project_id=project_links.get(str(item["id"])),
            )
        )
    return rows


@router.put("/projects/{project_id}/repo", response_model=GitHubRepositorySummary)
def link_repository_to_project(
    project_id: UUID,
    payload: GitHubRepositoryLink,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> GitHubRepositorySummary:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    integration = _integration(db, user.id)
    token = _token(db, integration)
    remote = _request_json("GET", f"{API_URL}/repos/{payload.full_name}", token)
    if not isinstance(remote, dict) or remote.get("id") != payload.repository_id:
        raise HTTPException(status_code=422, detail="Repository identity does not match GitHub")
    if bool(remote.get("private", False)):
        raise HTTPException(status_code=403, detail="Only public repositories are supported by this OAuth scope")
    repo_id = str(remote["id"])
    row = db.scalar(
        select(ProjectRepository).where(
            ProjectRepository.project_id == project.id,
            ProjectRepository.provider == PROVIDER,
            ProjectRepository.external_repo_id == repo_id,
        )
    )
    pushed_at = remote.get("pushed_at") if isinstance(remote.get("pushed_at"), str) else None
    if row is None:
        row = ProjectRepository(
            user_id=user.id,
            project_id=project.id,
            provider=PROVIDER,
            external_repo_id=repo_id,
            repo_url=str(remote["html_url"]),
            last_activity_at=datetime.fromisoformat(pushed_at.replace("Z", "+00:00")) if pushed_at else None,
            last_synced_at=datetime.now(UTC),
        )
        db.add(row)
    else:
        row.repo_url = str(remote["html_url"])
        row.last_activity_at = datetime.fromisoformat(pushed_at.replace("Z", "+00:00")) if pushed_at else None
        row.last_synced_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return GitHubRepositorySummary(
        id=int(remote["id"]),
        name=str(remote.get("name") or ""),
        full_name=str(remote.get("full_name") or ""),
        html_url=str(remote.get("html_url") or ""),
        private=bool(remote.get("private", False)),
        default_branch=str(remote.get("default_branch") or "main"),
        pushed_at=pushed_at,
        linked_project_id=str(row.project_id),
    )


@router.get("/projects/{project_id}/activity", response_model=list[GitHubActivitySummary])
def project_github_activity(
    project_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[GitHubActivitySummary]:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    integration = _integration(db, user.id)
    token = _token(db, integration)
    repos = list(
        db.scalars(
            select(ProjectRepository).where(
                ProjectRepository.user_id == user.id,
                ProjectRepository.project_id == project_id,
                ProjectRepository.provider == PROVIDER,
            )
        ).all()
    )
    output: list[GitHubActivitySummary] = []
    for repo in repos:
        full_name = repo.repo_url.rstrip("/").removeprefix("https://github.com/")
        if "/" not in full_name or not full_name:
            continue
        commits = _request_json("GET", f"{API_URL}/repos/{full_name}/commits", token, params={"per_page": "1"})
        pulls = _request_json(
            "GET", f"{API_URL}/repos/{full_name}/pulls", token, params={"state": "open", "per_page": "100"}
        )
        latest_sha = None
        latest_message = None
        latest_at = None
        if isinstance(commits, list) and commits and isinstance(commits[0], dict):
            commit = commits[0]
            latest_sha = commit.get("sha") if isinstance(commit.get("sha"), str) else None
            inner = commit.get("commit") if isinstance(commit.get("commit"), dict) else {}
            latest_message = inner.get("message") if isinstance(inner.get("message"), str) else None
            author = inner.get("author") if isinstance(inner.get("author"), dict) else {}
            latest_at = author.get("date") if isinstance(author.get("date"), str) else None
        if not isinstance(pulls, list):
            pulls = []
        repo.latest_commit_sha = latest_sha
        repo.last_activity_at = datetime.fromisoformat(latest_at.replace("Z", "+00:00")) if latest_at else repo.last_activity_at
        repo.last_synced_at = datetime.now(UTC)
        output.append(
            GitHubActivitySummary(
                repository=full_name,
                html_url=repo.repo_url,
                default_branch="main",
                latest_commit_sha=latest_sha,
                latest_commit_message=latest_message,
                latest_commit_at=latest_at,
                open_pull_requests=len(pulls),
                last_synced_at=repo.last_synced_at.isoformat() if repo.last_synced_at else None,
            )
        )
    db.commit()
    return output
