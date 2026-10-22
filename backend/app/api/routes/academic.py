from urllib.parse import urlparse
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.models_academic import (
    AcademicItem,
    Project,
    ProjectMilestone,
    ProjectStage,
    ResourceLink,
    StudyTopic,
    Subject,
    TaskResult,
)
from app.models_tasks import Task
from app.academic_schemas import (
    AcademicItemCreate,
    AcademicItemRead,
    AcademicItemUpdate,
    MilestoneCreate,
    MilestoneRead,
    MilestoneUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectStageCreate,
    ProjectStageRead,
    ProjectStageUpdate,
    ProjectUpdate,
    ResourceCreate,
    ResourceRead,
    StudyTopicRead,
    StudyTopicUpsert,
    SubjectCreate,
    SubjectRead,
    SubjectUpdate,
    TaskResultCreate,
    TaskResultRead,
)

router = APIRouter(tags=["studies and projects"])


def owned_subject(db: Session, user_id: UUID, subject_id: UUID) -> Subject:
    subject = db.scalar(
        select(Subject).where(Subject.id == subject_id, Subject.user_id == user_id)
    )
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


def owned_project(db: Session, user_id: UUID, project_id: UUID) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def owned_stage(db: Session, user_id: UUID, stage_id: UUID) -> ProjectStage:
    stage = db.scalar(
        select(ProjectStage).where(
            ProjectStage.id == stage_id,
            ProjectStage.user_id == user_id,
        )
    )
    if stage is None:
        raise HTTPException(status_code=404, detail="Project stage not found")
    return stage


def owned_milestone(db: Session, user_id: UUID, milestone_id: UUID) -> ProjectMilestone:
    milestone = db.scalar(
        select(ProjectMilestone).where(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.user_id == user_id,
        )
    )
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return milestone


def validate_http_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise HTTPException(status_code=422, detail="URL must use http or https")
    return url.strip()


@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[Subject]:
    return list(
        db.scalars(
            select(Subject)
            .where(Subject.user_id == user.id)
            .order_by(Subject.semester.desc(), Subject.name.asc())
        ).all()
    )


@router.post("/subjects", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Subject:
    data = payload.model_dump()
    data["name"] = data["name"].strip()
    data["semester"] = data["semester"].strip()
    if not data["name"] or not data["semester"]:
        raise HTTPException(status_code=422, detail="Subject name and semester are required")
    subject = Subject(user_id=user.id, **data)
    db.add(subject)
    try:
        db.commit()
        db.refresh(subject)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Subject already exists for this semester") from exc
    return subject


@router.patch("/subjects/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: UUID,
    payload: SubjectUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Subject:
    subject = owned_subject(db, user.id, subject_id)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("name", "semester"):
        if field in changes and changes[field] is not None:
            changes[field] = changes[field].strip()
            if not changes[field]:
                raise HTTPException(status_code=422, detail=f"{field} cannot be blank")
    for key, value in changes.items():
        setattr(subject, key, value)
    try:
        db.commit()
        db.refresh(subject)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Subject update conflicts with an existing record") from exc
    return subject


@router.get("/subjects/{subject_id}/topics", response_model=list[StudyTopicRead])
def list_study_topics(
    subject_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[StudyTopic]:
    owned_subject(db, user.id, subject_id)
    return list(
        db.scalars(
            select(StudyTopic)
            .where(StudyTopic.user_id == user.id, StudyTopic.subject_id == subject_id)
            .order_by(StudyTopic.name.asc())
        ).all()
    )


@router.put("/subjects/{subject_id}/topics", response_model=StudyTopicRead)
def upsert_study_topic(
    subject_id: UUID,
    payload: StudyTopicUpsert,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> StudyTopic:
    owned_subject(db, user.id, subject_id)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Topic name cannot be blank")
    topic = db.scalar(
        select(StudyTopic).where(
            StudyTopic.user_id == user.id,
            StudyTopic.subject_id == subject_id,
            StudyTopic.name == name,
        )
    )
    if topic is None:
        topic = StudyTopic(user_id=user.id, subject_id=subject_id, name=name)
        db.add(topic)
    topic.status = payload.status
    topic.notes = payload.notes
    topic.updated_at = datetime.now(UTC)
    try:
        db.commit()
        db.refresh(topic)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Topic update conflict") from exc
    return topic


@router.get("/subjects/{subject_id}/items", response_model=list[AcademicItemRead])
def list_academic_items(
    subject_id: UUID,
    item_status: str | None = Query(default=None, alias="status", pattern="^(todo|in_progress|submitted|completed|cancelled)$"),
    limit: int = Query(default=200, ge=1, le=500),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[AcademicItem]:
    owned_subject(db, user.id, subject_id)
    query = select(AcademicItem).where(
        AcademicItem.user_id == user.id,
        AcademicItem.subject_id == subject_id,
    )
    if item_status is not None:
        query = query.where(AcademicItem.status == item_status)
    return list(
        db.scalars(query.order_by(AcademicItem.due_at.asc().nulls_last()).limit(limit)).all()
    )


@router.post(
    "/subjects/{subject_id}/items",
    response_model=AcademicItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_academic_item(
    subject_id: UUID,
    payload: AcademicItemCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> AcademicItem:
    owned_subject(db, user.id, subject_id)
    data = payload.model_dump()
    data["title"] = data["title"].strip()
    if not data["title"]:
        raise HTTPException(status_code=422, detail="Item title cannot be blank")
    if data.get("resource_url"):
        data["resource_url"] = validate_http_url(data["resource_url"])
    item = AcademicItem(user_id=user.id, subject_id=subject_id, **data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/academic-items/{item_id}", response_model=AcademicItemRead)
def update_academic_item(
    item_id: UUID,
    payload: AcademicItemUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> AcademicItem:
    item = db.scalar(
        select(AcademicItem).where(AcademicItem.id == item_id, AcademicItem.user_id == user.id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Academic item not found")
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes and changes["title"] is not None:
        changes["title"] = changes["title"].strip()
        if not changes["title"]:
            raise HTTPException(status_code=422, detail="Item title cannot be blank")
    if changes.get("resource_url"):
        changes["resource_url"] = validate_http_url(changes["resource_url"])
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(
    include_archived: bool = False,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[Project]:
    query = select(Project).where(Project.user_id == user.id)
    if not include_archived:
        query = query.where(Project.status != "archived")
    return list(db.scalars(query.order_by(Project.updated_at.desc())).all())


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Project:
    data = payload.model_dump()
    data["name"] = data["name"].strip()
    if not data["name"]:
        raise HTTPException(status_code=422, detail="Project name cannot be blank")
    project = Project(user_id=user.id, **data)
    db.add(project)
    try:
        db.commit()
        db.refresh(project)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project name already exists") from exc
    return project


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Project:
    project = owned_project(db, user.id, project_id)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(status_code=422, detail="Project name cannot be blank")
    for key, value in changes.items():
        setattr(project, key, value)
    try:
        db.commit()
        db.refresh(project)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project update conflicts with an existing record") from exc
    return project


@router.get("/projects/{project_id}/stages", response_model=list[ProjectStageRead])
def list_project_stages(
    project_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[ProjectStage]:
    owned_project(db, user.id, project_id)
    return list(
        db.scalars(
            select(ProjectStage)
            .where(ProjectStage.user_id == user.id, ProjectStage.project_id == project_id)
            .order_by(ProjectStage.position.asc())
        ).all()
    )


@router.post(
    "/projects/{project_id}/stages",
    response_model=ProjectStageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_stage(
    project_id: UUID,
    payload: ProjectStageCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> ProjectStage:
    owned_project(db, user.id, project_id)
    data = payload.model_dump()
    data["name"] = data["name"].strip()
    if not data["name"]:
        raise HTTPException(status_code=422, detail="Stage name cannot be blank")
    stage = ProjectStage(user_id=user.id, project_id=project_id, **data)
    db.add(stage)
    try:
        db.commit()
        db.refresh(stage)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Stage position already exists") from exc
    return stage


@router.patch("/project-stages/{stage_id}", response_model=ProjectStageRead)
def update_project_stage(
    stage_id: UUID,
    payload: ProjectStageUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> ProjectStage:
    stage = owned_stage(db, user.id, stage_id)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(status_code=422, detail="Stage name cannot be blank")
    for key, value in changes.items():
        setattr(stage, key, value)
    try:
        db.commit()
        db.refresh(stage)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Stage position already exists") from exc
    return stage


@router.get("/projects/{project_id}/milestones", response_model=list[MilestoneRead])
def list_project_milestones(
    project_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[ProjectMilestone]:
    owned_project(db, user.id, project_id)
    return list(
        db.scalars(
            select(ProjectMilestone)
            .where(
                ProjectMilestone.user_id == user.id,
                ProjectMilestone.project_id == project_id,
            )
            .order_by(ProjectMilestone.due_at.asc().nulls_last())
        ).all()
    )


@router.post(
    "/projects/{project_id}/milestones",
    response_model=MilestoneRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_milestone(
    project_id: UUID,
    payload: MilestoneCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> ProjectMilestone:
    owned_project(db, user.id, project_id)
    data = payload.model_dump()
    data["title"] = data["title"].strip()
    if not data["title"]:
        raise HTTPException(status_code=422, detail="Milestone title cannot be blank")
    milestone = ProjectMilestone(user_id=user.id, project_id=project_id, **data)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.patch("/project-milestones/{milestone_id}", response_model=MilestoneRead)
def update_project_milestone(
    milestone_id: UUID,
    payload: MilestoneUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> ProjectMilestone:
    milestone = owned_milestone(db, user.id, milestone_id)
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes and changes["title"] is not None:
        changes["title"] = changes["title"].strip()
        if not changes["title"]:
            raise HTTPException(status_code=422, detail="Milestone title cannot be blank")
    for key, value in changes.items():
        setattr(milestone, key, value)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.get("/resources", response_model=list[ResourceRead])
def list_resources(
    subject_id: UUID | None = None,
    project_id: UUID | None = None,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[ResourceLink]:
    query = select(ResourceLink).where(ResourceLink.user_id == user.id)
    if subject_id is not None:
        owned_subject(db, user.id, subject_id)
        query = query.where(ResourceLink.subject_id == subject_id)
    if project_id is not None:
        owned_project(db, user.id, project_id)
        query = query.where(ResourceLink.project_id == project_id)
    if subject_id is not None and project_id is not None:
        raise HTTPException(status_code=422, detail="Choose either a subject or a project filter")
    return list(db.scalars(query.order_by(ResourceLink.created_at.desc())).all())


@router.post("/resources", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
def create_resource(
    payload: ResourceCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> ResourceLink:
    if (payload.subject_id is None) == (payload.project_id is None):
        raise HTTPException(status_code=422, detail="Provide exactly one parent: subject_id or project_id")
    if payload.subject_id:
        owned_subject(db, user.id, payload.subject_id)
    if payload.project_id:
        owned_project(db, user.id, payload.project_id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Resource title cannot be blank")
    resource = ResourceLink(
        user_id=user.id,
        title=title,
        url=validate_http_url(payload.url),
        resource_type=payload.resource_type,
        subject_id=payload.subject_id,
        project_id=payload.project_id,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.post("/task-results", response_model=TaskResultRead, status_code=status.HTTP_201_CREATED)
def create_task_result(
    payload: TaskResultCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TaskResult:
    task = db.scalar(select(Task).where(Task.id == payload.task_id, Task.user_id == user.id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if payload.project_id:
        owned_project(db, user.id, payload.project_id)
        if task.project_id != payload.project_id:
            raise HTTPException(status_code=422, detail="Task is not linked to this project")
    result = TaskResult(user_id=user.id, **payload.model_dump())
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


@router.get("/task-results", response_model=list[TaskResultRead])
def list_task_results(
    project_id: UUID | None = None,
    limit: int = Query(default=200, ge=1, le=500),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[TaskResult]:
    query = select(TaskResult).where(TaskResult.user_id == user.id)
    if project_id is not None:
        owned_project(db, user.id, project_id)
        query = query.where(TaskResult.project_id == project_id)
    return list(db.scalars(query.order_by(TaskResult.completed_at.desc()).limit(limit)).all())
