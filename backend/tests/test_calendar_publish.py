from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.api.routes import calendar as calendar_routes


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, results: list) -> None:
        self.results = iter(results)
        self.committed = False
        self.refreshed = False

    def scalar(self, _statement):
        return next(self.results)

    def commit(self) -> None:
        self.committed = True

    def refresh(self, _value) -> None:
        self.refreshed = True


class FakeGoogleClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def get(self, url: str, **kwargs):
        self.calls.append(("GET", {"url": url, **kwargs}))
        return next(self.responses)

    def post(self, url: str, **kwargs):
        self.calls.append(("POST", {"url": url, **kwargs}))
        return next(self.responses)

    def patch(self, url: str, **kwargs):
        self.calls.append(("PATCH", {"url": url, **kwargs}))
        return next(self.responses)


def make_context(event=None):
    user_id = uuid4()
    integration = SimpleNamespace(id=uuid4())
    selection = SimpleNamespace(calendar_id="primary", selected=True)
    if event is None:
        event = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            title="Lecture",
            description="Algorithms",
            start_at=datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
            end_at=datetime(2026, 11, 2, 11, 0, tzinfo=UTC),
            all_day=False,
            google_calendar_id=None,
            google_event_id=None,
            google_etag=None,
            google_updated_at=None,
            sync_status="local",
        )
    db = FakeSession([event, integration, selection])
    user = SimpleNamespace(id=user_id)
    return db, user, integration, event


def install_google_client(monkeypatch, client: FakeGoogleClient) -> None:
    monkeypatch.setattr(calendar_routes, "get_access_token", lambda *_args: "access-token")
    monkeypatch.setattr(calendar_routes.httpx, "Client", lambda **_kwargs: client)


def test_publish_event_creates_google_event(monkeypatch) -> None:
    db, user, _integration, event = make_context()
    client = FakeGoogleClient(
        [
            FakeResponse({"items": [{"id": "primary", "accessRole": "writer"}]}),
            FakeResponse(
                {
                    "id": "google-event-1",
                    "etag": '"version-1"',
                    "updated": "2026-11-01T10:00:00Z",
                }
            ),
        ]
    )
    install_google_client(monkeypatch, client)

    result = calendar_routes.publish_event_to_google(event.id, "primary", db, user)

    assert result is event
    assert event.google_calendar_id == "primary"
    assert event.google_event_id == "google-event-1"
    assert event.google_etag == '"version-1"'
    assert event.sync_status == "synced"
    assert db.committed and db.refreshed
    assert [method for method, _ in client.calls] == ["GET", "POST"]


def test_publish_event_rejects_read_only_google_calendar(monkeypatch) -> None:
    db, user, _integration, event = make_context()
    client = FakeGoogleClient(
        [FakeResponse({"items": [{"id": "primary", "accessRole": "reader"}]})]
    )
    install_google_client(monkeypatch, client)

    with pytest.raises(HTTPException) as error:
        calendar_routes.publish_event_to_google(event.id, "primary", db, user)

    assert error.value.status_code == 403
    assert event.google_event_id is None
    assert not db.committed
    assert [method for method, _ in client.calls] == ["GET"]


def test_publish_event_detects_external_etag_change(monkeypatch) -> None:
    event = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        title="Lecture",
        description=None,
        start_at=datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
        end_at=datetime(2026, 11, 2, 11, 0, tzinfo=UTC),
        all_day=False,
        google_calendar_id="primary",
        google_event_id="google-event-1",
        google_etag='"old-version"',
        google_updated_at=None,
        sync_status="pending",
    )
    db, user, _integration, event = make_context(event)
    client = FakeGoogleClient(
        [
            FakeResponse({"items": [{"id": "primary", "accessRole": "owner"}]}),
            FakeResponse({"etag": '"new-version"'}),
        ]
    )
    install_google_client(monkeypatch, client)

    with pytest.raises(HTTPException) as error:
        calendar_routes.publish_event_to_google(event.id, "primary", db, user)

    assert error.value.status_code == 409
    assert event.sync_status == "conflict"
    assert db.committed
    assert [method for method, _ in client.calls] == ["GET", "GET"]



def make_linked_event():
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        title="Lecture",
        description=None,
        start_at=datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
        end_at=datetime(2026, 11, 2, 11, 0, tzinfo=UTC),
        all_day=False,
        google_calendar_id="primary",
        google_event_id="google-event-1",
        google_etag='"version-1"',
        google_updated_at=None,
        sync_status="pending",
    )


def test_publish_event_marks_conflict_on_precondition_failed(monkeypatch) -> None:
    event = make_linked_event()
    db, user, _integration, event = make_context(event)
    client = FakeGoogleClient(
        [
            FakeResponse({"items": [{"id": "primary", "accessRole": "writer"}]}),
            FakeResponse({"etag": '"version-1"'}),
            FakeResponse({}, status_code=412),
        ]
    )
    install_google_client(monkeypatch, client)

    with pytest.raises(HTTPException) as error:
        calendar_routes.publish_event_to_google(event.id, "primary", db, user)

    assert error.value.status_code == 409
    assert event.sync_status == "conflict"
    assert db.committed
    assert [method for method, _ in client.calls] == ["GET", "GET", "PATCH"]
    patch_headers = client.calls[-1][1]["headers"]
    assert patch_headers["If-Match"] == '"version-1"'


def test_publish_event_marks_error_on_network_failure(monkeypatch) -> None:
    db, user, _integration, event = make_context()

    class FailingGoogleClient(FakeGoogleClient):
        def post(self, url: str, **kwargs):
            self.calls.append(("POST", {"url": url, **kwargs}))
            request = httpx.Request("POST", url)
            raise httpx.ConnectError("connection failed", request=request)

    client = FailingGoogleClient(
        [FakeResponse({"items": [{"id": "primary", "accessRole": "writer"}]})]
    )
    install_google_client(monkeypatch, client)

    with pytest.raises(HTTPException) as error:
        calendar_routes.publish_event_to_google(event.id, "primary", db, user)

    assert error.value.status_code == 502
    assert event.sync_status == "error"
    assert db.committed
    assert [method for method, _ in client.calls] == ["GET", "POST"]


def test_resolve_event_from_google_accepts_remote_version(monkeypatch) -> None:
    event = make_linked_event()
    db, user, _integration, event = make_context(event)
    client = FakeGoogleClient(
        [
            FakeResponse(
                {
                    "summary": "Updated lecture",
                    "description": "Updated details",
                    "etag": '"version-2"',
                    "updated": "2026-11-01T12:00:00Z",
                    "start": {"dateTime": "2026-11-03T12:00:00+03:00"},
                    "end": {"dateTime": "2026-11-03T13:30:00+03:00"},
                }
            )
        ]
    )
    install_google_client(monkeypatch, client)

    result = calendar_routes.resolve_event_from_google(event.id, db, user)

    assert result is event
    assert event.title == "Updated lecture"
    assert event.description == "Updated details"
    assert event.start_at == datetime(2026, 11, 3, 12, 0, tzinfo=__import__("datetime").timezone(__import__("datetime").timedelta(hours=3)))
    assert event.end_at == datetime(2026, 11, 3, 13, 30, tzinfo=__import__("datetime").timezone(__import__("datetime").timedelta(hours=3)))
    assert event.google_etag == '"version-2"'
    assert event.sync_status == "synced"
    assert db.committed and db.refreshed
    assert [method for method, _ in client.calls] == ["GET"]


def test_resolve_event_from_google_rejects_invalid_interval(monkeypatch) -> None:
    event = make_linked_event()
    db, user, _integration, event = make_context(event)
    original_title = event.title
    client = FakeGoogleClient(
        [
            FakeResponse(
                {
                    "summary": "Updated lecture",
                    "etag": '"version-2"',
                    "start": {"dateTime": "2026-11-03T12:00:00"},
                    "end": {"dateTime": "2026-11-03T13:00:00Z"},
                }
            )
        ]
    )
    install_google_client(monkeypatch, client)

    with pytest.raises(HTTPException) as error:
        calendar_routes.resolve_event_from_google(event.id, db, user)

    assert error.value.status_code == 502
    assert event.title == original_title
    assert not db.committed