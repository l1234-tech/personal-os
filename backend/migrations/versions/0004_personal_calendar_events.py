"""Add user-owned calendar events independent from external providers."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_personal_calendar_events"
down_revision: str | None = "0003_calendar_integrations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personal_calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("color", sa.String(length=24), nullable=False, server_default="blue"),
        sa.Column("google_calendar_id", sa.String(length=1024), nullable=True),
        sa.Column("google_event_id", sa.String(length=1024), nullable=True),
        sa.Column("sync_status", sa.String(length=24), nullable=False, server_default="local"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_personal_calendar_events_user_id", "personal_calendar_events", ["user_id"])
    op.create_index(
        "ix_personal_calendar_events_owner_start",
        "personal_calendar_events",
        ["user_id", "start_at"],
    )
    op.create_index(
        "ix_personal_calendar_events_owner_end",
        "personal_calendar_events",
        ["user_id", "end_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_personal_calendar_events_owner_end", table_name="personal_calendar_events")
    op.drop_index("ix_personal_calendar_events_owner_start", table_name="personal_calendar_events")
    op.drop_index("ix_personal_calendar_events_user_id", table_name="personal_calendar_events")
    op.drop_table("personal_calendar_events")
