"""Store Google Calendar event version metadata for safe outbound updates."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_google_event_version"
down_revision: str | None = "0004_personal_calendar_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "personal_calendar_events",
        sa.Column("google_etag", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "personal_calendar_events",
        sa.Column("google_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("personal_calendar_events", "google_updated_at")
    op.drop_column("personal_calendar_events", "google_etag")
