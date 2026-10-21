"""Add provider integrations and Google Calendar sync tables."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_calendar_integrations"
down_revision: str | None = "0002_tasks_time"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=48), nullable=False),
        sa.Column("external_account_id", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column(
            "connected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "provider", name="uq_integrations_user_provider"),
    )
    op.create_index("ix_integrations_user_id", "integrations", ["user_id"], unique=False)
    op.create_index(
        "ix_integrations_owner_status", "integrations", ["user_id", "status"], unique=False
    )

    op.create_table(
        "integration_credentials",
        sa.Column(
            "integration_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_type", sa.String(length=32), nullable=False, server_default="Bearer"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "oauth_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=48), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("state_hash", name="uq_oauth_states_state_hash"),
    )
    op.create_index("ix_oauth_states_user_id", "oauth_states", ["user_id"], unique=False)
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"], unique=False)

    op.create_table(
        "sync_cursors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=300), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "integration_id", "resource_type", name="uq_sync_cursors_resource"
        ),
    )
    op.create_index("ix_sync_cursors_integration_id", "sync_cursors", ["integration_id"], unique=False)

    op.create_table(
        "calendar_selections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calendar_id", sa.String(length=1024), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "integration_id", "calendar_id", name="uq_calendar_selection_external_id"
        ),
    )
    op.create_index(
        "ix_calendar_selections_integration_id",
        "calendar_selections",
        ["integration_id"],
        unique=False,
    )

    op.create_table(
        "calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calendar_id", sa.String(length=1024), nullable=False),
        sa.Column("external_event_id", sa.String(length=1024), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False, server_default="(без названия)"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="confirmed"),
        sa.Column("html_link", sa.Text(), nullable=True),
        sa.Column("external_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "integration_id",
            "calendar_id",
            "external_event_id",
            name="uq_calendar_events_external_id",
        ),
    )
    op.create_index("ix_calendar_events_user_id", "calendar_events", ["user_id"], unique=False)
    op.create_index("ix_calendar_events_integration_id", "calendar_events", ["integration_id"], unique=False)
    op.create_index(
        "ix_calendar_events_owner_start", "calendar_events", ["user_id", "start_at"], unique=False
    )
    op.create_index(
        "ix_calendar_events_owner_status", "calendar_events", ["user_id", "status"], unique=False
    )

    op.create_table(
        "task_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calendar_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["calendar_event_id"], ["calendar_events.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_task_blocks_idempotency"),
    )
    op.create_index("ix_task_blocks_user_id", "task_blocks", ["user_id"], unique=False)
    op.create_index("ix_task_blocks_task_id", "task_blocks", ["task_id"], unique=False)
    op.create_index(
        "ix_task_blocks_owner_start", "task_blocks", ["user_id", "start_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_task_blocks_owner_start", table_name="task_blocks")
    op.drop_index("ix_task_blocks_task_id", table_name="task_blocks")
    op.drop_index("ix_task_blocks_user_id", table_name="task_blocks")
    op.drop_table("task_blocks")

    op.drop_index("ix_calendar_events_owner_status", table_name="calendar_events")
    op.drop_index("ix_calendar_events_owner_start", table_name="calendar_events")
    op.drop_index("ix_calendar_events_integration_id", table_name="calendar_events")
    op.drop_index("ix_calendar_events_user_id", table_name="calendar_events")
    op.drop_table("calendar_events")

    op.drop_index("ix_calendar_selections_integration_id", table_name="calendar_selections")
    op.drop_table("calendar_selections")

    op.drop_index("ix_sync_cursors_integration_id", table_name="sync_cursors")
    op.drop_table("sync_cursors")

    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_index("ix_oauth_states_user_id", table_name="oauth_states")
    op.drop_table("oauth_states")

    op.drop_table("integration_credentials")
    op.drop_index("ix_integrations_owner_status", table_name="integrations")
    op.drop_index("ix_integrations_user_id", table_name="integrations")
    op.drop_table("integrations")
