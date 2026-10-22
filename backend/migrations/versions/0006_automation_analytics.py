"""Create audit, background job, outbox and notification tables."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_automation_analytics"
down_revision: str | None = "0005_studies_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_column(name: str, primary_key: bool = False, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        postgresql.UUID(as_uuid=True),
        primary_key=primary_key,
        nullable=nullable,
    )


def created_column() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        uuid_column("id", primary_key=True),
        uuid_column("user_id", nullable=True),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        created_column(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_background_jobs_user_id", "background_jobs", ["user_id"])
    op.create_index("ix_background_jobs_status_run_after", "background_jobs", ["status", "run_after"])
    op.create_index("ix_background_jobs_owner_created", "background_jobs", ["user_id", "created_at"])

    op.create_table(
        "outbox_events",
        uuid_column("id", primary_key=True),
        uuid_column("user_id", nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        created_column(),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_outbox_events_user_id", "outbox_events", ["user_id"])
    op.create_index("ix_outbox_events_status_created", "outbox_events", ["status", "created_at"])

    op.create_table(
        "notifications",
        uuid_column("id", primary_key=True),
        uuid_column("user_id"),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        created_column(),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_owner_created", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notifications_owner_status", "notifications", ["user_id", "status"])

    op.create_table(
        "telegram_link_tokens",
        uuid_column("id", primary_key=True),
        uuid_column("user_id"),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        created_column(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_telegram_link_tokens_user_id", "telegram_link_tokens", ["user_id"])
    op.create_index("ix_telegram_link_tokens_expires_at", "telegram_link_tokens", ["expires_at"])

    op.create_table(
        "telegram_accounts",
        uuid_column("id", primary_key=True),
        uuid_column("user_id"),
        sa.Column("telegram_chat_id", sa.String(64), nullable=False, unique=True),
        sa.Column("telegram_user_id", sa.String(64), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_telegram_accounts_user_id", "telegram_accounts", ["user_id"])

    op.create_table(
        "audit_log",
        uuid_column("id", primary_key=True),
        uuid_column("user_id", nullable=True),
        sa.Column("actor_type", sa.String(24), nullable=False, server_default="user"),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        created_column(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_owner_created", "audit_log", ["user_id", "created_at"])


def downgrade() -> None:
    for table, indexes in [
        ("audit_log", ["ix_audit_log_owner_created", "ix_audit_log_user_id"]),
        ("telegram_accounts", ["ix_telegram_accounts_user_id"]),
        ("telegram_link_tokens", ["ix_telegram_link_tokens_expires_at", "ix_telegram_link_tokens_user_id"]),
        ("notifications", ["ix_notifications_owner_status", "ix_notifications_owner_created", "ix_notifications_user_id"]),
        ("outbox_events", ["ix_outbox_events_status_created", "ix_outbox_events_user_id"]),
        ("background_jobs", ["ix_background_jobs_owner_created", "ix_background_jobs_status_run_after", "ix_background_jobs_user_id"]),
    ]:
        for index in indexes:
            op.drop_index(index, table_name=table)
    for table in (
        "audit_log",
        "telegram_accounts",
        "telegram_link_tokens",
        "notifications",
        "outbox_events",
        "background_jobs",
    ):
        op.drop_table(table)
