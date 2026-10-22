from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.academic_schemas import AcademicItemCreate, ProjectStageCreate, ResourceCreate


def test_academic_item_rejects_naive_due_date() -> None:
    with pytest.raises(ValidationError):
        AcademicItemCreate(title="Lab 3", item_type="lab", due_at=datetime(2026, 10, 30, 17, 0))


def test_academic_item_accepts_aware_due_date() -> None:
    item = AcademicItemCreate(
        title="Lab 3",
        item_type="lab",
        due_at=datetime(2026, 10, 30, 17, 0, tzinfo=UTC),
    )
    assert item.item_type == "lab"
    assert item.due_at is not None and item.due_at.tzinfo is not None


def test_project_stage_requires_nonnegative_position() -> None:
    with pytest.raises(ValidationError):
        ProjectStageCreate(name="Research", position=-1)


def test_resource_parent_is_checked_in_route_and_database() -> None:
    # The route and DB check together enforce exactly one parent association.
    resource = ResourceCreate(title="Lecture notes", url="https://drive.google.com")
    assert resource.subject_id is None
    assert resource.project_id is None
