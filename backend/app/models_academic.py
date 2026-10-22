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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("user_id", "name", "semester", name="uq_subject_owner_name_semester"),
        Index("ix_subjects_owner_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    semester: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class StudyTopic(Base):
    __tablename__ = "study_topics"
    __table_args__ = (
        UniqueConstraint("subject_id", "name", name="uq_study_topic_subject_name"),
        CheckConstraint(
            "status IN ('not_started', 'learning', 'practicing', 'mastered')",
            name="ck_study_topics_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_started", server_default="not_started")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AcademicItem(Base):
    __tablename__ = "academic_items"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('lab', 'homework', 'exam', 'test', 'project', 'other')",
            name="ck_academic_items_type",
        ),
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'submitted', 'completed', 'cancelled')",
            name="ck_academic_items_status",
        ),
        Index("ix_academic_items_owner_due", "user_id", "due_at"),
        Index("ix_academic_items_subject_status", "subject_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    item_type: Mapped[str] = mapped_column(String(24), nullable=False, default="other", server_default="other")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="todo", server_default="todo")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "project_type IN ('ml', 'software', 'study', 'personal', 'other')",
            name="ck_projects_type",
        ),
        CheckConstraint(
            "status IN ('idea', 'research', 'development', 'testing', 'completed', 'paused', 'archived')",
            name="ck_projects_status",
        ),
        UniqueConstraint("user_id", "name", name="uq_projects_owner_name"),
        Index("ix_projects_owner_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_type: Mapped[str] = mapped_column(String(24), nullable=False, default="other", server_default="other")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="idea", server_default="idea")
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProjectStage(Base):
    __tablename__ = "project_stages"
    __table_args__ = (
        UniqueConstraint("project_id", "position", name="uq_project_stage_position"),
        CheckConstraint("position >= 0", name="ck_project_stage_position"),
        CheckConstraint(
            "status IN ('not_started', 'in_progress', 'completed', 'blocked')",
            name="ck_project_stage_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started", server_default="not_started")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"
    __table_args__ = (
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'completed', 'cancelled')",
            name="ck_project_milestones_status",
        ),
        Index("ix_project_milestones_owner_due", "user_id", "due_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="todo", server_default="todo")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProjectRepository(Base):
    __tablename__ = "project_repositories"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "provider", "external_repo_id", name="uq_project_repository_external"
        ),
        Index("ix_project_repositories_project", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(24), nullable=False, default="github")
    external_repo_id: Mapped[str] = mapped_column(String(160), nullable=False)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ResourceLink(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint(
            "(subject_id IS NOT NULL AND project_id IS NULL) OR "
            "(subject_id IS NULL AND project_id IS NOT NULL)",
            name="ck_resources_single_parent",
        ),
        Index("ix_resources_owner", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False, default="link")
    subject_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TaskResult(Base):
    __tablename__ = "task_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    result_type: Mapped[str] = mapped_column(String(40), nullable=False, default="note")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
