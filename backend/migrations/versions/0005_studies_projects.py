"""Create university and project tracking tables and project time links."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_studies_projects"
down_revision: str | None = "0004_tutoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid(name: str, primary_key: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), primary_key=primary_key, nullable=False)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def _updated() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "subjects",
        _uuid("id", True),
        _uuid("user_id"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("semester", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        _created(),
        _updated(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "name", "semester", name="uq_subject_owner_name_semester"),
    )
    op.create_index("ix_subjects_user_id", "subjects", ["user_id"])
    op.create_index("ix_subjects_owner_status", "subjects", ["user_id", "status"])

    op.create_table(
        "study_topics",
        _uuid("id", True),
        _uuid("user_id"),
        _uuid("subject_id"),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="not_started"),
        sa.Column("notes", sa.Text(), nullable=True),
        _updated(),
        sa.CheckConstraint(
            "status IN ('not_started', 'learning', 'practicing', 'mastered')",
            name="ck_study_topics_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("subject_id", "name", name="uq_study_topic_subject_name"),
    )
    op.create_index("ix_study_topics_user_id", "study_topics", ["user_id"])
    op.create_index("ix_study_topics_subject_id", "study_topics", ["subject_id"])

    op.create_table(
        "academic_items",
        _uuid("id", True),
        _uuid("user_id"),
        _uuid("subject_id"),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("item_type", sa.String(24), nullable=False, server_default="other"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="todo"),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("resource_url", sa.Text(), nullable=True),
        _created(),
        _updated(),
        sa.CheckConstraint(
            "item_type IN ('lab', 'homework', 'exam', 'test', 'project', 'other')",
            name="ck_academic_items_type",
        ),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'submitted', 'completed', 'cancelled')",
            name="ck_academic_items_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_academic_items_user_id", "academic_items", ["user_id"])
    op.create_index("ix_academic_items_subject_id", "academic_items", ["subject_id"])
    op.create_index("ix_academic_items_owner_due", "academic_items", ["user_id", "due_at"])
    op.create_index("ix_academic_items_subject_status", "academic_items", ["subject_id", "status"])

    op.create_table(
        "projects",
        _uuid("id", True),
        _uuid("user_id"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_type", sa.String(24), nullable=False, server_default="other"),
        sa.Column("status", sa.String(24), nullable=False, server_default="idea"),
        sa.Column("goal", sa.Text(), nullable=True),
        _created(),
        _updated(),
        sa.CheckConstraint(
            "project_type IN ('ml', 'software', 'study', 'personal', 'other')",
            name="ck_projects_type",
        ),
        sa.CheckConstraint(
            "status IN ('idea', 'research', 'development', 'testing', 'completed', 'paused', 'archived')",
            name="ck_projects_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "name", name="uq_projects_owner_name"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_owner_status", "projects", ["user_id", "status"])

    op.create_table(
        "project_stages",
        _uuid("id", True),
        _uuid("user_id"),
        _uuid("project_id"),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("position >= 0", name="ck_project_stage_position"),
        sa.CheckConstraint(
            "status IN ('not_started', 'in_progress', 'completed', 'blocked')",
            name="ck_project_stage_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "position", name="uq_project_stage_position"),
    )
    op.create_index("ix_project_stages_user_id", "project_stages", ["user_id"])
    op.create_index("ix_project_stages_project_id", "project_stages", ["project_id"])

    op.create_table(
        "project_milestones",
        _uuid("id", True),
        _uuid("user_id"),
        _uuid("project_id"),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="todo"),
        sa.Column("result", sa.Text(), nullable=True),
        _created(),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'completed', 'cancelled')",
            name="ck_project_milestones_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_project_milestones_user_id", "project_milestones", ["user_id"])
    op.create_index("ix_project_milestones_project_id", "project_milestones", ["project_id"])
    op.create_index(
        "ix_project_milestones_owner_due", "project_milestones", ["user_id", "due_at"]
    )

    op.create_table(
        "project_repositories",
        _uuid("id", True),
        _uuid("user_id"),
        _uuid("project_id"),
        sa.Column("provider", sa.String(24), nullable=False, server_default="github"),
        sa.Column("external_repo_id", sa.String(160), nullable=False),
        sa.Column("repo_url", sa.Text(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_commit_sha", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "project_id", "provider", "external_repo_id", name="uq_project_repository_external"
        ),
    )
    op.create_index("ix_project_repositories_user_id", "project_repositories", ["user_id"])
    op.create_index("ix_project_repositories_project_id", "project_repositories", ["project_id"])

    op.create_table(
        "resources",
        _uuid("id", True),
        _uuid("user_id"),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=False, server_default="link"),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        _created(),
        sa.CheckConstraint(
            "(subject_id IS NOT NULL AND project_id IS NULL) OR "
            "(subject_id IS NULL AND project_id IS NOT NULL)",
            name="ck_resources_single_parent",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_resources_user_id", "resources", ["user_id"])
    op.create_index("ix_resources_subject_id", "resources", ["subject_id"])
    op.create_index("ix_resources_project_id", "resources", ["project_id"])

    op.create_table(
        "task_results",
        _uuid("id", True),
        _uuid("user_id"),
        _uuid("task_id"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_type", sa.String(40), nullable=False, server_default="note"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resource_url", sa.Text(), nullable=True),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_task_results_user_id", "task_results", ["user_id"])
    op.create_index("ix_task_results_task_id", "task_results", ["task_id"])
    op.create_index("ix_task_results_project_id", "task_results", ["project_id"])

    for table in ("tasks", "time_entries", "timer_sessions"):
        op.add_column(table, sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_project_id_projects",
            table,
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])


def downgrade() -> None:
    for table in ("tasks", "time_entries", "timer_sessions"):
        op.drop_index(f"ix_{table}_project_id", table_name=table)
        op.drop_constraint(f"fk_{table}_project_id_projects", table, type_="foreignkey")
        op.drop_column(table, "project_id")

    for table, indexes in [
        ("task_results", ["ix_task_results_project_id", "ix_task_results_task_id", "ix_task_results_user_id"]),
        ("resources", ["ix_resources_project_id", "ix_resources_subject_id", "ix_resources_user_id"]),
        ("project_repositories", ["ix_project_repositories_project_id", "ix_project_repositories_user_id"]),
        ("project_milestones", ["ix_project_milestones_owner_due", "ix_project_milestones_project_id", "ix_project_milestones_user_id"]),
        ("project_stages", ["ix_project_stages_project_id", "ix_project_stages_user_id"]),
        ("projects", ["ix_projects_owner_status", "ix_projects_user_id"]),
        ("academic_items", ["ix_academic_items_subject_status", "ix_academic_items_owner_due", "ix_academic_items_subject_id", "ix_academic_items_user_id"]),
        ("study_topics", ["ix_study_topics_subject_id", "ix_study_topics_user_id"]),
        ("subjects", ["ix_subjects_owner_status", "ix_subjects_user_id"]),
    ]:
        for index in indexes:
            op.drop_index(index, table_name=table)
    for table in (
        "task_results",
        "resources",
        "project_repositories",
        "project_milestones",
        "project_stages",
        "projects",
        "academic_items",
        "study_topics",
        "subjects",
    ):
        op.drop_table(table)
