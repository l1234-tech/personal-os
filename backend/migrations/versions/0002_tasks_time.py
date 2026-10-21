"""Create tasks, time entries and persistent timer sessions."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_tasks_time"
down_revision: str | None = "0001_auth_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="todo"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="personal"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="ck_tasks_estimate_positive",
        ),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'done', 'cancelled')",
            name="ck_tasks_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="ck_tasks_priority",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"], unique=False)
    op.create_index(
        "ix_tasks_owner_status_due", "tasks", ["user_id", "status", "due_at"], unique=False
    )

    op.create_table(
        "time_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="personal"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "duration_seconds >= 0", name="ck_time_entries_duration_nonnegative"
        ),
        sa.CheckConstraint(
            "source IN ('timer', 'manual', 'calendar_adjustment')",
            name="ck_time_entries_source",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_time_entries_user_id", "time_entries", ["user_id"], unique=False)
    op.create_index("ix_time_entries_task_id", "time_entries", ["task_id"], unique=False)
    op.create_index(
        "ix_time_entries_owner_start", "time_entries", ["user_id", "started_at"], unique=False
    )

    op.create_table(
        "timer_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="personal"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('running', 'paused', 'stopped')", name="ck_timer_sessions_status"
        ),
        sa.CheckConstraint(
            "elapsed_seconds >= 0", name="ck_timer_sessions_elapsed_nonnegative"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["time_entry_id"], ["time_entries.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_timer_sessions_user_id", "timer_sessions", ["user_id"], unique=False)
    op.create_index("ix_timer_sessions_task_id", "timer_sessions", ["task_id"], unique=False)
    op.create_index(
        "uq_timer_sessions_one_active_per_user",
        "timer_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('running', 'paused')"),
    )


def downgrade() -> None:
    op.drop_index("uq_timer_sessions_one_active_per_user", table_name="timer_sessions")
    op.drop_index("ix_timer_sessions_task_id", table_name="timer_sessions")
    op.drop_index("ix_timer_sessions_user_id", table_name="timer_sessions")
    op.drop_table("timer_sessions")

    op.drop_index("ix_time_entries_owner_start", table_name="time_entries")
    op.drop_index("ix_time_entries_task_id", table_name="time_entries")
    op.drop_index("ix_time_entries_user_id", table_name="time_entries")
    op.drop_table("time_entries")

    op.drop_index("ix_tasks_owner_status_due", table_name="tasks")
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_table("tasks")
