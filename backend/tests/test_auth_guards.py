import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_me_requires_a_session_cookie() -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_invitation_bootstrap_is_disabled_without_server_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "bootstrap_invitation_secret", None)
    response = client.post(
        "/api/v1/auth/invitations",
        json={"email": "person@example.com"},
    )
    assert response.status_code == 404


def test_logout_without_session_is_idempotent() -> None:
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
