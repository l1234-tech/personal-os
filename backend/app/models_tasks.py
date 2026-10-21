from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("estimated_minutes IS NULL OR estimated_minutes > 0", name="ck_tasks_estimate_positive"),
        CheckConstraint("status IN ('todo', 'in_progress', 'done', 'cancelled')", name="ck_tasks_status"),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'urgent')", name="ck_tasks_priority"),
        Index("ix_tasks_owner_status_due", "user_id", "status", "due_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="todo", server_default="todo")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium", server_default="medium")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="personal", server_default="personal")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class TimeEntry(Base):
    __tablename__ = "time_entries"
    __table_args__ = (
        CheckConstraint("duration_seconds >= 0", name="ck_time_entries_duration_nonnegative"),
        CheckConstraint(
            "source IN ('timer', 'manual', 'calendar_adjustment')", name="ck_time_entries_source"
        ),
        Index("ix_time_entries_owner_start", "user_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="personal")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TimerSession(Base):
    __tablename__ = "timer_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'paused', 'stopped')", name="ck_timer_sessions_status"),
        CheckConstraint("elapsed_seconds >= 0", name="ck_timer_sessions_elapsed_nonnegative"),
        Index(
            "uq_timer_sessions_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('running', 'paused')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="personal")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running", server_default="running")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_entry_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("time_entries.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
