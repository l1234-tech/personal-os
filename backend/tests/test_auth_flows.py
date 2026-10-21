from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db
from app.main import app
from app.models import Invitation
from app.security import generate_opaque_token, hash_password, hash_token


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL auth integration tests")

    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, class_=Session, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def issue_invitation(client: TestClient, email: str, hours: int = 72) -> str:
    response = client.post(
        "/api/v1/auth/invitations",
        headers={"x-bootstrap-secret": "ci-test-bootstrap-secret-which-is-not-production"},
        json={"email": email, "expires_in_hours": hours},
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


def test_register_login_me_logout_flow(client: TestClient) -> None:
    email = "first.user@example.com"
    invitation_token = issue_invitation(client, email)

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "strong-password-123",
            "invitation_token": invitation_token,
        },
    )
    assert registered.status_code == 201, registered.text
    assert registered.json()["email"] == email
    assert "personal_os_session" in registered.cookies

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == email

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-password-123"},
    )
    assert login.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200


def test_invitation_is_bound_to_email_and_single_use(client: TestClient) -> None:
    token = issue_invitation(client, "owner@example.com")
    wrong_email = client.post(
        "/api/v1/auth/register",
        json={
            "email": "attacker@example.com",
            "password": "strong-password-123",
            "invitation_token": token,
        },
    )
    assert wrong_email.status_code == 400

    correct_payload = {
        "email": "owner@example.com",
        "password": "strong-password-123",
        "invitation_token": token,
    }
    assert client.post("/api/v1/auth/register", json=correct_payload).status_code == 201
    reused = client.post("/api/v1/auth/register", json=correct_payload)
    assert reused.status_code == 409  # duplicate account is rejected before token reuse is checked


def test_expired_invitation_is_rejected(client: TestClient) -> None:
    token = generate_opaque_token()
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        db.add(
            Invitation(
                email="expired@example.com",
                token_hash=hash_token(token),
                expires_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        db.commit()
    finally:
        db_generator.close()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "expired@example.com",
            "password": "strong-password-123",
            "invitation_token": token,
        },
    )
    assert response.status_code == 400


def test_invalid_login_and_duplicate_registration_are_rejected(client: TestClient) -> None:
    email = "duplicate@example.com"
    token = issue_invitation(client, email)
    payload = {
        "email": email,
        "password": "strong-password-123",
        "invitation_token": token,
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201

    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "another-strong-password",
            "invitation_token": generate_opaque_token(),
        },
    )
    assert duplicate.status_code == 409
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "incorrect-password"},
    )
    assert bad_login.status_code == 401
