from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ItemType = Literal["lab", "homework", "exam", "test", "project", "other"]
ItemStatus = Literal["todo", "in_progress", "submitted", "completed", "cancelled"]
ProjectType = Literal["ml", "software", "study", "personal", "other"]
ProjectStatus = Literal["idea", "research", "development", "testing", "completed", "paused", "archived"]
StageStatus = Literal["not_started", "in_progress", "completed", "blocked"]
MilestoneStatus = Literal["todo", "in_progress", "completed", "cancelled"]
MasteryStatus = Literal["not_started", "learning", "practicing", "mastered"]


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    semester: str = Field(min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=10000)


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    semester: str | None = Field(default=None, min_length=1, max_length=80)
    status: Literal["active", "paused", "completed", "archived"] | None = None
    notes: str | None = Field(default=None, max_length=10000)


class SubjectRead(BaseModel):
    id: UUID
    name: str
    semester: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StudyTopicUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    status: MasteryStatus = "not_started"
    notes: str | None = Field(default=None, max_length=10000)


class StudyTopicRead(BaseModel):
    id: UUID
    subject_id: UUID
    name: str
    status: str
    notes: str | None
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AcademicItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    item_type: ItemType = "other"
    description: str | None = Field(default=None, max_length=10000)
    due_at: datetime | None = None
    status: ItemStatus = "todo"
    result: str | None = Field(default=None, max_length=10000)
    resource_url: str | None = Field(default=None, max_length=2048)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        return aware(value) if value is not None else None


class AcademicItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    item_type: ItemType | None = None
    description: str | None = Field(default=None, max_length=10000)
    due_at: datetime | None = None
    status: ItemStatus | None = None
    result: str | None = Field(default=None, max_length=10000)
    resource_url: str | None = Field(default=None, max_length=2048)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        return aware(value) if value is not None else None


class AcademicItemRead(BaseModel):
    id: UUID
    subject_id: UUID
    title: str
    item_type: str
    description: str | None
    due_at: datetime | None
    status: str
    result: str | None
    resource_url: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    project_type: ProjectType = "other"
    status: ProjectStatus = "idea"
    goal: str | None = Field(default=None, max_length=10000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    goal: str | None = Field(default=None, max_length=10000)


class ProjectRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    project_type: str
    status: str
    goal: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProjectStageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    position: int = Field(ge=0, le=1000)
    status: StageStatus = "not_started"
    notes: str | None = Field(default=None, max_length=10000)


class ProjectStageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    position: int | None = Field(default=None, ge=0, le=1000)
    status: StageStatus | None = None
    notes: str | None = Field(default=None, max_length=10000)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        return aware(value) if value is not None else None


class ProjectStageRead(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    position: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    notes: str | None
    model_config = ConfigDict(from_attributes=True)


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_at: datetime | None = None
    status: MilestoneStatus = "todo"
    result: str | None = Field(default=None, max_length=10000)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        return aware(value) if value is not None else None


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    due_at: datetime | None = None
    status: MilestoneStatus | None = None
    result: str | None = Field(default=None, max_length=10000)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        return aware(value) if value is not None else None


class MilestoneRead(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    due_at: datetime | None
    status: str
    result: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=2048)
    resource_type: str = Field(default="link", min_length=1, max_length=40)
    subject_id: UUID | None = None
    project_id: UUID | None = None


class ResourceRead(BaseModel):
    id: UUID
    title: str
    url: str
    resource_type: str
    subject_id: UUID | None
    project_id: UUID | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TaskResultCreate(BaseModel):
    task_id: UUID
    project_id: UUID | None = None
    result_type: str = Field(default="note", min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=10000)
    resource_url: str | None = Field(default=None, max_length=2048)


class TaskResultRead(BaseModel):
    id: UUID
    task_id: UUID
    project_id: UUID | None
    result_type: str
    description: str | None
    resource_url: str | None
    completed_at: datetime
    model_config = ConfigDict(from_attributes=True)
