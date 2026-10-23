"""Add owner-scoped finance transactions.

Revision ID: 0003_finance_transactions
Revises: 0002_tasks_time
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_finance_transactions"
down_revision: str | None = "0002_tasks_time"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finance_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_finance_transactions_amount_positive"),
        sa.CheckConstraint("kind IN ('income', 'expense')", name="ck_finance_transactions_kind"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_finance_transactions_user_id", "finance_transactions", ["user_id"])
    op.create_index("ix_finance_transactions_user_date", "finance_transactions", ["user_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_finance_transactions_user_date", table_name="finance_transactions")
    op.drop_index("ix_finance_transactions_user_id", table_name="finance_transactions")
    op.drop_table("finance_transactions")
