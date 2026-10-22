"""Regression tests for the persistent timer's core invariants.

These tests exercise schema/transition expectations without requiring a live
PostgreSQL instance. Database-level concurrency is enforced by the partial
unique index in migration 0002_tasks_time.
"""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.api.routes.timer import to_timer_read


def test_running_timer_includes_time_since_last_resume() -> None:
    now = datetime(2026, 10, 22, 12, 5, tzinfo=UTC)
    session = SimpleNamespace(
        id="12345678-1234-5678-1234-567812345678",
        task_id=None,
        category="study",
        started_at=now - timedelta(minutes=10),
        status="running",
        elapsed_seconds=120,
        last_resumed_at=now - timedelta(seconds=30),
        finished_at=None,
    )

    result = to_timer_read(session, now)

    assert result.elapsed_seconds == 150
    assert result.status == "running"


def test_paused_timer_does_not_accumulate_wall_clock_time() -> None:
    now = datetime(2026, 10, 22, 12, 5, tzinfo=UTC)
    session = SimpleNamespace(
        id="12345678-1234-5678-1234-567812345678",
        task_id=None,
        category="study",
        started_at=now - timedelta(minutes=10),
        status="paused",
        elapsed_seconds=120,
        last_resumed_at=None,
        finished_at=None,
    )

    result = to_timer_read(session, now)

    assert result.elapsed_seconds == 120
    assert result.status == "paused"


def test_running_timer_clamps_negative_clock_delta() -> None:
    now = datetime(2026, 10, 22, 12, 5, tzinfo=UTC)
    session = SimpleNamespace(
        id="12345678-1234-5678-1234-567812345678",
        task_id=None,
        category="study",
        started_at=now,
        status="running",
        elapsed_seconds=120,
        last_resumed_at=now + timedelta(seconds=20),
        finished_at=None,
    )

    result = to_timer_read(session, now)

    assert result.elapsed_seconds == 120
