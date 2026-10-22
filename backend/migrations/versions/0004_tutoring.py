"""Create tutoring CRM and add student links to recorded work."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_tutoring"
down_revision: str | None = "0003_calendar_integrations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid(name: str, *, primary_key: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), primary_key=primary_key, nullable=False)


def _created() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def upgrade() -> None:
    op.create_table(
        "students",
        _uuid("id", primary_key=True),
        _uuid("user_id"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(120), nullable=False),
        sa.Column("rate_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        _created(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("status IN ('active', 'paused', 'archived')", name="ck_students_status"),
        sa.CheckConstraint("rate_amount >= 0", name="ck_students_rate_nonnegative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_students_user_id", "students", ["user_id"])
    op.create_index("ix_students_owner_status", "students", ["user_id", "status"])

    op.create_table(
        "lessons",
        _uuid("id", primary_key=True),
        _uuid("user_id"),
        _uuid("student_id"),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        _created(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled', 'rescheduled', 'no_show')",
            name="ck_lessons_status",
        ),
        sa.CheckConstraint("price_amount >= 0", name="ck_lessons_price_nonnegative"),
        sa.CheckConstraint("scheduled_end > scheduled_start", name="ck_lessons_schedule_interval"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_lessons_user_id", "lessons", ["user_id"])
    op.create_index("ix_lessons_student_id", "lessons", ["student_id"])
    op.create_index("ix_lessons_owner_start", "lessons", ["user_id", "scheduled_start"])
    op.create_index("ix_lessons_student_status", "lessons", ["student_id", "status"])

    op.create_table(
        "lesson_topics",
        _uuid("id", primary_key=True),
        _uuid("lesson_id"),
        sa.Column("topic", sa.String(300), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        _created(),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_lesson_topics_lesson_id", "lesson_topics", ["lesson_id"])

    op.create_table(
        "homework",
        _uuid("id", primary_key=True),
        _uuid("user_id"),
        _uuid("student_id"),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="assigned"),
        sa.Column("result_notes", sa.Text(), nullable=True),
        _created(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('assigned', 'in_progress', 'submitted', 'reviewed', 'cancelled')",
            name="ck_homework_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_homework_user_id", "homework", ["user_id"])
    op.create_index("ix_homework_student_id", "homework", ["student_id"])
    op.create_index("ix_homework_lesson_id", "homework", ["lesson_id"])
    op.create_index("ix_homework_owner_due", "homework", ["student_id", "due_at"])

    op.create_table(
        "student_progress",
        _uuid("id", primary_key=True),
        _uuid("user_id"),
        _uuid("student_id"),
        sa.Column("topic", sa.String(300), nullable=False),
        sa.Column("mastery_status", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "mastery_status IN ('not_started', 'learning', 'practicing', 'mastered')",
            name="ck_student_progress_mastery",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_student_progress_user_id", "student_progress", ["user_id"])
    op.create_index("ix_student_progress_student_id", "student_progress", ["student_id"])
    op.create_index(
        "uq_student_progress_topic", "student_progress", ["student_id", "topic"], unique=True
    )

    op.create_table(
        "payments",
        _uuid("id", primary_key=True),
        _uuid("user_id"),
        _uuid("student_id"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _created(),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_student_id", "payments", ["student_id"])
    op.create_index("ix_payments_owner_paid_at", "payments", ["user_id", "paid_at"])
    op.create_index("ix_payments_student_paid_at", "payments", ["student_id", "paid_at"])

    op.create_table(
        "payment_allocations",
        _uuid("id", primary_key=True),
        _uuid("user_id"),
        _uuid("payment_id"),
        _uuid("lesson_id"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        _created(),
        sa.CheckConstraint("amount > 0", name="ck_payment_allocations_amount_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_payment_allocations_user_id", "payment_allocations", ["user_id"])
    op.create_index("ix_payment_allocations_payment_id", "payment_allocations", ["payment_id"])
    op.create_index("ix_payment_allocations_lesson_id", "payment_allocations", ["lesson_id"])
    op.create_index(
        "uq_payment_allocation_pair", "payment_allocations", ["payment_id", "lesson_id"], unique=True
    )

    op.create_table(
        "lesson_status_history",
        _uuid("id", primary_key=True),
        _uuid("user_id"),
        _uuid("lesson_id"),
        sa.Column("old_status", sa.String(20), nullable=False),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_lesson_status_history_user_id", "lesson_status_history", ["user_id"])
    op.create_index("ix_lesson_status_history_lesson_id", "lesson_status_history", ["lesson_id"])

    op.add_column(
        "time_entries",
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_time_entries_student_id_students",
        "time_entries",
        "students",
        ["student_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_time_entries_student_id", "time_entries", ["student_id"])

    op.add_column(
        "timer_sessions",
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_timer_sessions_student_id_students",
        "timer_sessions",
        "students",
        ["student_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_timer_sessions_student_id", "timer_sessions", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_timer_sessions_student_id", table_name="timer_sessions")
    op.drop_constraint(
        "fk_timer_sessions_student_id_students", "timer_sessions", type_="foreignkey"
    )
    op.drop_column("timer_sessions", "student_id")
    op.drop_index("ix_time_entries_student_id", table_name="time_entries")
    op.drop_constraint("fk_time_entries_student_id_students", "time_entries", type_="foreignkey")
    op.drop_column("time_entries", "student_id")

    for table, indexes in [
        ("lesson_status_history", ["ix_lesson_status_history_lesson_id", "ix_lesson_status_history_user_id"]),
        ("payment_allocations", ["uq_payment_allocation_pair", "ix_payment_allocations_lesson_id", "ix_payment_allocations_payment_id", "ix_payment_allocations_user_id"]),
        ("payments", ["ix_payments_student_paid_at", "ix_payments_owner_paid_at", "ix_payments_student_id", "ix_payments_user_id"]),
        ("student_progress", ["uq_student_progress_topic", "ix_student_progress_student_id", "ix_student_progress_user_id"]),
        ("homework", ["ix_homework_owner_due", "ix_homework_lesson_id", "ix_homework_student_id", "ix_homework_user_id"]),
        ("lesson_topics", ["ix_lesson_topics_lesson_id"]),
        ("lessons", ["ix_lessons_student_status", "ix_lessons_owner_start", "ix_lessons_student_id", "ix_lessons_user_id"]),
        ("students", ["ix_students_owner_status", "ix_students_user_id"]),
    ]:
        for index in indexes:
            op.drop_index(index, table_name=table)
    for table in [
        "lesson_status_history",
        "payment_allocations",
        "payments",
        "student_progress",
        "homework",
        "lesson_topics",
        "lessons",
        "students",
    ]:
        op.drop_table(table)
